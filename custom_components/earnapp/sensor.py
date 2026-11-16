import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)
from .const import DOMAIN, CONF_OAUTH_TOKEN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=15)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EarnApp sensors based on a config entry."""
    token = entry.data[CONF_OAUTH_TOKEN]
    session = async_get_clientsession(hass)

    async def async_update_data():
        """Fetch data from EarnApp API."""
        headers = {
            "Cookie": f"auth-method=google; oauth-token={token}",
            "Accept": "application/json",
        }
        try:
            async with session.get(
                "https://earnapp.com/dashboard/api/money?appid=earnapp",
                headers=headers,
            ) as money_resp:
                if money_resp.status != 200:
                    raise UpdateFailed(f"Money API error: {money_resp.status}")
                money_data = await money_resp.json()

            async with session.get(
                "https://earnapp.com/dashboard/api/devices?appid=earnapp",
                headers=headers,
            ) as dev_resp:
                devices_data = await dev_resp.json() if dev_resp.status == 200 else []

            return {
                "money": money_data,
                "devices": devices_data,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with EarnApp API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="earnapp",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([
        EarnAppBalanceSensor(coordinator, entry),
        EarnAppTotalEarnedSensor(coordinator, entry),
        EarnAppDevicesSensor(coordinator, entry),
    ])


class EarnAppBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for EarnApp sensors."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id


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
        devs = self.coordinator.data.get("devices", [])
        return len(devs) if isinstance(devs, list) else 0

    @property
    def extra_state_attributes(self):
        devs = self.coordinator.data.get("devices", [])
        if not isinstance(devs, list):
            return {}
        return {
            "devices": [
                {
                    "uuid": d.get("uuid"),
                    "title": d.get("title"),
                    "type": d.get("device_type"),
                    "bw": d.get("bw"),
                    "earned": d.get("earned"),
                }
                for d in devs
            ]
        }
