"""Config flow for TastyIgniter Alerts."""
import logging
import voluptuous as vol

from tastyigniter import TastyIgniter

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TastyIgniter."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        config_entry = self.hass.config_entries.async_entries(DOMAIN)
        if config_entry:
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            domain = user_input[CONF_HOST]

            api_client = TastyIgniter(username, password, domain)

            try:
                await api_client.get_enabled_locations()
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[f"{CONF_USERNAME}_{CONF_HOST}"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"TastyIgniter - {CONF_HOST}", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )
