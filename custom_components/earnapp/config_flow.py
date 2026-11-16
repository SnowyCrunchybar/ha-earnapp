from urllib.parse import quote, unquote

import voluptuous as vol
from aiohttp import ClientError

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
            clean_refresh, error = await self._async_validate_tokens(user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="EarnApp",
                    data={
                        CONF_REFRESH_TOKEN: clean_refresh,
                        CONF_XSRF_TOKEN: user_input[CONF_XSRF_TOKEN].strip(),
                    },
                )

        data_schema = vol.Schema({
            vol.Required(CONF_REFRESH_TOKEN): str,
            vol.Required(CONF_XSRF_TOKEN): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reauth(self, _entry_data):
        """Handle reauthentication for an existing entry."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Confirm new credentials for an existing entry."""
        errors = {}
        if user_input is not None:
            clean_refresh, error = await self._async_validate_tokens(user_input)
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        CONF_REFRESH_TOKEN: clean_refresh,
                        CONF_XSRF_TOKEN: user_input[CONF_XSRF_TOKEN].strip(),
                    },
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_REFRESH_TOKEN): str,
                vol.Required(CONF_XSRF_TOKEN): str,
            }),
            errors=errors,
        )

    async def _async_validate_tokens(self, user_input):
        """Validate tokens against the EarnApp API."""
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

        try:
            async with session.get(
                "https://earnapp.com/dashboard/api/money?appid=earnapp",
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    return None, "invalid_auth"
        except (ClientError, TypeError, ValueError):
            return None, "cannot_connect"

        return clean_refresh, None
