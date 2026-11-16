from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


def _today_str() -> str:
    """Return today's UTC date string matching EarnApp usage keys (YYYY-MM-DD)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _dev_id(device: dict) -> str | None:
    """Return device identifier supporting both uuid and _id."""
    return device.get("uuid") or device.get("_id")


def _dev_title(device: dict, fallback_id: str) -> str:
    """Return human-readable device title supporting both title and name."""
    return device.get("title") or device.get("name") or fallback_id[:8]


def _dev_platform(device: dict, dev_id: str) -> tuple[str, str]:
    """Return (platform_label, mdi_icon) based on device_type or ID prefix."""
    raw_type = (device.get("device_type") or "").lower()
    prefix = dev_id.lower()

    if "android" in raw_type or prefix.startswith("sdk-android"):
        return ("Android (Phone)", "mdi:cellphone")
    if "ios" in raw_type or "iphone" in raw_type or prefix.startswith("sdk-ios"):
        return ("iOS (Phone/Tablet)", "mdi:cellphone")
    if "win" in raw_type or prefix.startswith("sdk-win"):
        return ("Windows (PC)", "mdi:microsoft-windows")
    if "mac" in raw_type or prefix.startswith("sdk-mac"):
        return ("macOS (PC)", "mdi:apple")
    if "linux" in raw_type or prefix.startswith("sdk-linux"):
        return ("Linux (PC/Server)", "mdi:linux")

    return (device.get("device_type") or "Unknown", "mdi:desktop-tower")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EarnApp sensors based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        EarnAppBalanceSensor(coordinator, entry),
        EarnAppTotalEarnedSensor(coordinator, entry),
        EarnAppDevicesSensor(coordinator, entry),
        EarnAppTotalDailyUsageSensor(coordinator, entry),
    ]

    known_ids: set[str] = set()

    async_add_entities(entities)

    def async_add_new_devices() -> None:
        new_entities: list[SensorEntity] = []
        for device in coordinator.data.get("devices", []):
            dev_id = _dev_id(device)
            if dev_id and dev_id not in known_ids:
                known_ids.add(dev_id)
                new_entities.append(EarnAppSingleDeviceSensor(coordinator, entry, dev_id))
                new_entities.append(EarnAppDeviceDailyUsageSensor(coordinator, entry, dev_id))
                new_entities.append(EarnAppDevicePlatformSensor(coordinator, entry, dev_id))
                new_entities.append(EarnAppDeviceIpSensor(coordinator, entry, dev_id))
        if new_entities:
            async_add_entities(new_entities)

    async_add_new_devices()
    coordinator.async_add_listener(async_add_new_devices)


class EarnAppBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for EarnApp sensors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="EarnApp",
            manufacturer="EarnApp",
        )


class EarnAppBalanceSensor(EarnAppBaseSensor):
    """Current available balance."""

    _attr_name = "EarnApp Balance"
    _attr_icon = "mdi:currency-usd"
    _attr_native_unit_of_measurement = "$"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_balance"

    @property
    def native_value(self):
        return self.coordinator.data["money"].get("balance")


class EarnAppTotalEarnedSensor(EarnAppBaseSensor):
    """Total earnings all time."""

    _attr_name = "EarnApp Total Earned"
    _attr_icon = "mdi:cash-plus"
    _attr_native_unit_of_measurement = "$"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_total_earned"

    @property
    def native_value(self):
        return self.coordinator.data["money"].get("earnings_total")


class EarnAppDevicesSensor(EarnAppBaseSensor):
    """Active devices count and details."""

    _attr_name = "EarnApp Active Devices"
    _attr_icon = "mdi:devices"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_devices"

    @property
    def native_value(self):
        return len(self.coordinator.data.get("devices", []))

    @property
    def extra_state_attributes(self):
        return {
            "statuses": self.coordinator.data.get("statuses", {}),
            "devices": [
                {
                    "uuid": _dev_id(d),
                    "title": _dev_title(d, _dev_id(d) or ""),
                    "platform": _dev_platform(d, _dev_id(d) or "")[0],
                    "ip": d.get("ip"),
                    "bw": d.get("bw"),
                    "earned": d.get("earned"),
                }
                for d in self.coordinator.data.get("devices", [])
            ],
        }


class EarnAppTotalDailyUsageSensor(EarnAppBaseSensor):
    """Combined daily bandwidth usage across all devices (MB)."""

    _attr_name = "EarnApp Daily Usage Total"
    _attr_icon = "mdi:cloud-download"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_daily_usage_total"

    @property
    def native_value(self) -> float:
        today = _today_str()
        total_bytes = 0
        for dev_usage in self.coordinator.data.get("usage", {}).values():
            if isinstance(dev_usage, dict):
                total_bytes += dev_usage.get(today, 0)
        return round(total_bytes / (1024 * 1024), 2)


class EarnAppDeviceBase(EarnAppBaseSensor):
    """Base class for individual EarnApp device sensors."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, dev_id: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._dev_id = dev_id

    def _get_device_data(self) -> dict:
        for d in self.coordinator.data.get("devices", []):
            if _dev_id(d) == self._dev_id:
                return d
        return {}

    def _device_name(self) -> str:
        return _dev_title(self._get_device_data(), self._dev_id)

    @property
    def device_info(self) -> DeviceInfo:
        device = self._get_device_data()
        platform_label, _ = _dev_platform(device, self._dev_id)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_{self._dev_id}")},
            name=f"EarnApp {self._device_name()}",
            manufacturer="EarnApp",
            model=platform_label,
            via_device=(DOMAIN, self._entry_id),
        )


class EarnAppSingleDeviceSensor(EarnAppDeviceBase):
    """Individual EarnApp device earnings sensor."""

    _attr_native_unit_of_measurement = "$"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_device_{self._dev_id}"

    @property
    def name(self) -> str:
        return f"EarnApp {self._device_name()}"

    @property
    def icon(self) -> str:
        _, icon = _dev_platform(self._get_device_data(), self._dev_id)
        return icon

    @property
    def native_value(self):
        return self._get_device_data().get("earned")

    @property
    def extra_state_attributes(self):
        device = self._get_device_data()
        platform_label, _ = _dev_platform(device, self._dev_id)
        return {
            "uuid": self._dev_id,
            "title": self._device_name(),
            "platform": platform_label,
            "bandwidth_bytes": device.get("bw"),
            "total_earned": device.get("earned_total"),
            "rate": device.get("rate"),
            "ip": device.get("ip"),
            "country": device.get("country"),
        }


class EarnAppDeviceDailyUsageSensor(EarnAppDeviceBase):
    """Daily bandwidth usage sensor (MB) for an individual EarnApp device."""

    _attr_icon = "mdi:swap-vertical"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_device_{self._dev_id}_daily_usage"

    @property
    def name(self) -> str:
        return f"EarnApp {self._device_name()} Daily Usage"

    @property
    def native_value(self) -> float:
        today = _today_str()
        dev_usage = self.coordinator.data.get("usage", {}).get(self._dev_id, {})
        bytes_today = dev_usage.get(today, 0) if isinstance(dev_usage, dict) else 0
        return round(bytes_today / (1024 * 1024), 2)

    @property
    def extra_state_attributes(self):
        dev_usage = self.coordinator.data.get("usage", {}).get(self._dev_id, {})
        return {
            "history_bytes": dev_usage if isinstance(dev_usage, dict) else {},
        }


class EarnAppDevicePlatformSensor(EarnAppDeviceBase):
    """Diagnostic sensor showing OS/device type (Windows, macOS, Linux, Android, iOS)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_device_{self._dev_id}_platform"

    @property
    def name(self) -> str:
        return f"EarnApp {self._device_name()} Platform"

    @property
    def icon(self) -> str:
        _, icon = _dev_platform(self._get_device_data(), self._dev_id)
        return icon

    @property
    def native_value(self) -> str:
        platform_label, _ = _dev_platform(self._get_device_data(), self._dev_id)
        return platform_label


class EarnAppDeviceIpSensor(EarnAppDeviceBase):
    """Diagnostic sensor showing the device's IP address."""

    _attr_icon = "mdi:ip-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_device_{self._dev_id}_ip"

    @property
    def name(self) -> str:
        return f"EarnApp {self._device_name()} IP"

    @property
    def native_value(self) -> str | None:
        return self._get_device_data().get("ip")

    @property
    def extra_state_attributes(self):
        device = self._get_device_data()
        return {
            "country": device.get("country"),
        }
