import logging
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)

from .const import DOMAIN, CONF_REFRESH_TOKEN, CONF_XSRF_TOKEN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EarnApp sensors based on a config entry."""
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    xsrf_token = entry.data[CONF_XSRF_TOKEN]
    session = async_get_clientsession(hass)

    async def async_update_data():
        """Fetch data from EarnApp API."""
        headers = {
            "Cookie": (
                f"auth-method=google; "
                f"oauth-refresh-token={refresh_token}; "
                f"xsrf-token={xsrf_token}"
            ),
            "x-xsrf-token": xsrf_token,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://earnapp.com/dashboard/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }
        try:
            async with session.get(
                "https://earnapp.com/dashboard/api/money?appid=earnapp",
                headers=headers,
            ) as money_resp:
                if money_resp.status == 401:
                    await hass.config_entries.async_start_reauth(
                        entry, data=entry.data
                    )
                if money_resp.status != 200:
                    raise UpdateFailed(f"Money API error: HTTP {money_resp.status}")
                money_data = await money_resp.json()

            async with session.get(
                "https://earnapp.com/dashboard/api/devices?appid=earnapp",
                headers=headers,
            ) as dev_resp:
                if dev_resp.status == 401:
                    await hass.config_entries.async_start_reauth(
                        entry, data=entry.data
                    )
                if dev_resp.status != 200:
                    raise UpdateFailed(f"Devices API error: HTTP {dev_resp.status}")
                devices_data = await dev_resp.json()
                if not isinstance(devices_data, list):
                    raise UpdateFailed("Devices API returned an invalid response")

            return {
                "money": money_data,
                "devices": devices_data,
            }
        except UpdateFailed:
            raise
        except (ClientError, TypeError, ValueError) as err:
            raise UpdateFailed(f"Error communicating with EarnApp API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="earnapp",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = [
        EarnAppBalanceSensor(coordinator, entry),
        EarnAppTotalEarnedSensor(coordinator, entry),
        EarnAppDevicesSensor(coordinator, entry),
    ]

    known_uuids: set[str] = set()

    async_add_entities(entities)

    def async_add_new_devices() -> None:
        new_entities = []
        for device in coordinator.data.get("devices", []):
            uuid = device.get("uuid")
            if uuid and uuid not in known_uuids:
                known_uuids.add(uuid)
                new_entities.append(EarnAppSingleDeviceSensor(coordinator, entry, uuid))
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

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_devices"

    @property
    def native_value(self):
        return len(self.coordinator.data.get("devices", []))

    @property
    def extra_state_attributes(self):
        return {
            "devices": [
                {
                    "uuid": d.get("uuid"),
                    "title": d.get("title"),
                    "type": d.get("device_type"),
                    "bw": d.get("bw"),
                    "earned": d.get("earned"),
                }
                for d in self.coordinator.data.get("devices", [])
            ]
        }


class EarnAppSingleDeviceSensor(EarnAppBaseSensor):
    """Individual EarnApp device sensor."""

    _attr_icon = "mdi:desktop-tower"
    _attr_native_unit_of_measurement = "$"

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, uuid: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._uuid = uuid

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_{self._uuid}")},
            name=self.name,
            manufacturer="EarnApp",
            model=self._get_device_data().get("device_type"),
        )

    def _get_device_data(self) -> dict:
        for d in self.coordinator.data.get("devices", []):
            if d.get("uuid") == self._uuid:
                return d
        return {}

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_device_{self._uuid}"

    @property
    def name(self) -> str:
        device = self._get_device_data()
        title = device.get("title") or self._uuid[:8]
        return f"EarnApp {title}"

    @property
    def native_value(self):
        return self._get_device_data().get("earned")

    @property
    def extra_state_attributes(self):
        device = self._get_device_data()
        return {
            "uuid": self._uuid,
            "title": device.get("title"),
            "device_type": device.get("device_type"),
            "bandwidth_bytes": device.get("bw"),
            "total_earned": device.get("earned_total"),
            "rate": device.get("rate"),
            "ip": device.get("ip"),
            "country": device.get("country"),
        }
