from urllib.parse import quote, unquote
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_REFRESH_TOKEN, CONF_XSRF_TOKEN


class EarnAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EarnApp."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            raw_refresh = user_input[CONF_REFRESH_TOKEN].strip()
            xsrf_token = user_input[CONF_XSRF_TOKEN].strip()

            clean_refresh = quote(unquote(raw_refresh), safe="")

            session = async_get_clientsession(self.hass)
            headers = {
                "Cookie": (
                    f"auth-method=google; "
                    f"oauth-refresh-token={clean_refresh}; "
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
            url = "https://earnapp.com/dashboard/api/money?appid=earnapp"

            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return self.async_create_entry(
                            title="EarnApp",
                            data={
                                CONF_REFRESH_TOKEN: clean_refresh,
                                CONF_XSRF_TOKEN: xsrf_token,
                            },
                        )
                    errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_REFRESH_TOKEN): str,
            vol.Required(CONF_XSRF_TOKEN): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
