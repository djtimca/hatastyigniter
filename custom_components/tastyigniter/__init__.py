"""The TastyIgniter Alerts integration."""
import asyncio
from datetime import timedelta
import logging

from tastyigniter import TastyIgniter
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST

from .const import COORDINATOR, DOMAIN, API

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the TastyIgniter component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up TastyIgniter from a config entry."""
    polling_interval = 30
    conf = entry.data

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    domain = conf[CONF_HOST]

    api = TastyIgniter(username, password, domain)

    try:
        await api.get_enabled_locations()
    except ConnectionError as error:
        _LOGGER.debug("TastyIgniter API Error: %s", error)
        return False
        raise ConfigEntryNotReady from error
    except ValueError as error:
        _LOGGER.debug("TastyIgniter API Error: %s", error)
        return False
        raise ConfigEntryNotReady from error

    coordinator = TastyIgniterCoordinator(
        hass,
        api=api,
        name="TastyIgniter",
        polling_interval=polling_interval,
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = {COORDINATOR: coordinator, API: api}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class TastyIgniterCoordinator(DataUpdateCoordinator):
    """Class to manage fetching update data from the TastyIgniter endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: str,
        name: str,
        polling_interval: int,
    ):
        """Initialize the global TastyIgniter data updater."""
        self.api = api
        self._open_orders = {}

        super().__init__(
            hass = hass,
            logger = _LOGGER,
            name = name,
            update_interval = timedelta(seconds=polling_interval),
        )

    async def _async_update_data(self):
        """Fetch data from TastyIgniter."""
        try:
            _LOGGER.debug("Updating the coordinator data.")
            locations = await self.api.get_locations()
            received_orders = await self.api.get_received_orders()
            
            current_orders = self._open_orders
            r_orders = {}
            self._open_orders = {}
            location_names = {}

            for location in locations:
                location_names[location["location_id"]] = location["location_name"]

            for order in received_orders:
                """Structure the dict for easy alerts."""
                r_orders[order["location_id"]] = order
                self._open_orders[order["order_id"]] = order

                if not current_orders.get(order["order_id"]):
                    event_data = {
                        "order_id": order["order_id"],
                        "location_id": order["location_id"],
                        "location_name": location_names[order["location_id"]],
                        "order_type": order["order_type"],
                        "order_time_is_asap": order["order_time_is_asap"],
                    }

                    self.hass.bus.async_fire("tastyigniter_neworder", event_data)


            return {
                "locations": locations,
                "orders": r_orders,
            }
        except ConnectionError as error:
            _LOGGER.info("TastyIgniter API: %s", error)
            raise UpdateFailed from error
        except ValueError as error:
            _LOGGER.info("TastyIgniter API: %s", error)
            raise UpdateFailed from error

        

