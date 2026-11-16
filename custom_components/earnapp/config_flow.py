import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_OAUTH_TOKEN

class EarnAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EarnApp."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            token = user_input[CONF_OAUTH_TOKEN].strip()
            session = async_get_clientsession(self.hass)
            headers = {
                "Cookie": f"auth-method=google; oauth-token={token}",
                "Accept": "application/json",
            }
            url = "https://earnapp.com/dashboard/api/money?appid=earnapp"

            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return self.async_create_entry(
                            title="EarnApp",
                            data={CONF_OAUTH_TOKEN: token},
                        )
                    else:
                        errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_OAUTH_TOKEN): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
