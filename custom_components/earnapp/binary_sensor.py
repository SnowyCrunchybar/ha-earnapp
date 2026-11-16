from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .sensor import _dev_id, _dev_platform, _dev_title


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EarnApp binary sensors based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def async_add_new_devices() -> None:
        new_entities: list[BinarySensorEntity] = []
        for device in coordinator.data.get("devices", []):
            dev_id = _dev_id(device)
            if dev_id and dev_id not in known_ids:
                known_ids.add(dev_id)
                new_entities.append(EarnAppDeviceOnlineSensor(coordinator, entry, dev_id))
        if new_entities:
            async_add_entities(new_entities)

    async_add_new_devices()
    coordinator.async_add_listener(async_add_new_devices)


class EarnAppDeviceOnlineSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether an EarnApp device is online."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, dev_id: str
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
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

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_device_{self._dev_id}_online"

    @property
    def name(self) -> str:
        return f"EarnApp {self._device_name()} Status"

    @property
    def is_on(self) -> bool | None:
        statuses = self.coordinator.data.get("statuses", {})
        if not isinstance(statuses, dict) or self._dev_id not in statuses:
            return None
        val = statuses[self._dev_id]
        if isinstance(val, bool):
            return val
        if isinstance(val, dict):
            return bool(
                val.get("online")
                or val.get("connected")
                or val.get("status") in ("online", "connected", "active")
            )
        if isinstance(val, str):
            return val.lower() in ("online", "connected", "active", "1", "true")
        return bool(val)

    @property
    def extra_state_attributes(self):
        statuses = self.coordinator.data.get("statuses", {})
        return {
            "raw_status": statuses.get(self._dev_id)
            if isinstance(statuses, dict)
            else None,
        }
