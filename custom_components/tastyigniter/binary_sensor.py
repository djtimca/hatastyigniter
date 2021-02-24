"""Definition and setup of the TastyIgniter Binary Sensors for Home Assistant."""

import logging
import time

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_NAME
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from . import TastyIgniterCoordinator
from .const import ATTR_IDENTIFIERS, ATTR_MANUFACTURER, ATTR_MODEL, DOMAIN, COORDINATOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platforms."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    sensors = []

    for location in coordinator.data["locations"]:
        sensors.append(
            TastyIgniterSensor(
                coordinator,
                location,
                "mdi:food",
                "ti_location",
            )
        )

    async_add_entities(sensors)


class TastyIgniterSensor(BinarySensorEntity):
    """Defines a TastyIgniter Binary sensor."""

    def __init__(
        self, 
        coordinator: TastyIgniterCoordinator, 
        location: dict,
        icon: str,
        device_identifier: str,
        ):
        """Initialize Entities."""

        self._name = location["location_name"]
        self._location_id = location["location_id"]
        self._unique_id = f"ti_{self._location_id}"
        self._state = None
        self._icon = icon
        self._device_identifier = device_identifier
        self.coordinator = coordinator

        telephone = location["location_telephone"].replace("-","")
        telephone = telephone.replace(" ","")
        if len(telephone) == 10:
            telephone = f"+1{telephone}"
        else:
            telephone = ""

        self.attrs = {"phone":telephone}

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return the unique Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def name(self):
        """Return the friendly name of this entity."""
        return self._name

    @property
    def icon(self):
        """Return the icon for this entity."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        return self.attrs

    @property
    def device_info(self):
        """Define the device based on device_identifier."""

        device_name = "TastyIgniter"
        device_model = "Order Alerts"

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_identifier)},
            ATTR_NAME: device_name,
            ATTR_MANUFACTURER: "TastyIgniter",
            ATTR_MODEL: device_model,
        }

    @property
    def is_on(self) -> bool:
        """Return the state."""
        order_data = self.coordinator.data["orders"]
        
        if order_data.get(self._location_id):
            return True
        else:
            return False

    async def async_update(self):
        """Update TastyIgniter Binary Sensor Entity."""
        await self.coordinator.async_request_refresh()
        
    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
