import logging
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_REFRESH_TOKEN, CONF_XSRF_TOKEN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor"]
SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EarnApp from a config entry."""
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
            "Content-Type": "application/json",
            "Referer": "https://earnapp.com/dashboard/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }
        try:
            # 1. Saldo ja kokonaistienestit
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

            # 2. Laitelistaus
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

            # 3. Päivittäinen datankäyttö (usage daily)
            usage_daily_map = {}
            async with session.get(
                "https://earnapp.com/dashboard/api/usage?appid=earnapp&step=daily",
                headers=headers,
            ) as usage_resp:
                if usage_resp.status == 200:
                    usage_raw = await usage_resp.json()
                    if isinstance(usage_raw, list):
                        for item in usage_raw:
                            dev_id = item.get("_id") or item.get("uuid")
                            if dev_id:
                                usage_daily_map[dev_id] = item.get("data", {})

            # 4. Kuukausittainen datankäyttö (usage monthly)
            usage_monthly_map = {}
            async with session.get(
                "https://earnapp.com/dashboard/api/usage?appid=earnapp&step=monthly",
                headers=headers,
            ) as monthly_resp:
                if monthly_resp.status == 200:
                    monthly_raw = await monthly_resp.json()
                    if isinstance(monthly_raw, list):
                        for item in monthly_raw:
                            dev_id = item.get("_id") or item.get("uuid")
                            if dev_id:
                                usage_monthly_map[dev_id] = item.get("data", {})

            # 5. Laitteiden online-tilat (POST device_statuses)
            statuses_data = None
            device_payload = [
                {"uuid": d.get("uuid") or d.get("_id")}
                for d in devices_data
                if d.get("uuid") or d.get("_id")
            ]
            async with session.post(
                "https://earnapp.com/dashboard/api/device_statuses?appid=earnapp&version=1.689.642",
                headers=headers,
                json={"devices": device_payload},
            ) as status_resp:
                if status_resp.status == 200:
                    statuses_raw = await status_resp.json()
                    if isinstance(statuses_raw, dict):
                        statuses_data = statuses_raw
                else:
                    body = await status_resp.text()
                    _LOGGER.warning(
                        "device_statuses returned HTTP %s: %s",
                        status_resp.status,
                        body[:200],
                    )

            # 6. CPU/GPU-laitteet ja tienestit
            cpu_gpu_map = {}
            async with session.get(
                "https://earnapp.com/dashboard/api/cpu_gpu_devices?appid=earnapp",
                headers=headers,
            ) as cg_dev_resp:
                if cg_dev_resp.status == 200:
                    cg_raw = await cg_dev_resp.json()
                    if isinstance(cg_raw, list):
                        for item in cg_raw:
                            dev_id = item.get("uuid") or item.get("_id")
                            if dev_id:
                                cpu_gpu_map[dev_id] = item

            # 7. CPU/GPU-päiväkäyttö
            cpu_gpu_usage_map = {}
            async with session.get(
                "https://earnapp.com/dashboard/api/cpu_gpu_usage?appid=earnapp&step=daily",
                headers=headers,
            ) as cg_usage_resp:
                if cg_usage_resp.status == 200:
                    cgu_raw = await cg_usage_resp.json()
                    if isinstance(cgu_raw, list):
                        for item in cgu_raw:
                            dev_id = item.get("_id") or item.get("uuid")
                            if dev_id:
                                cpu_gpu_usage_map[dev_id] = item.get("data", {})

            return {
                "money": money_data,
                "devices": devices_data,
                "usage_daily": usage_daily_map,
                "usage_monthly": usage_monthly_map,
                "statuses": statuses_data,
                "cpu_gpu_devices": cpu_gpu_map,
                "cpu_gpu_usage": cpu_gpu_usage_map,
            }
        except UpdateFailed:
            raise
        except (ClientError, TypeError, ValueError) as err:
            raise UpdateFailed(f"Error communicating with EarnApp API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
