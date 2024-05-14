"""Definition and setup of the TastyIgniter Binary Sensors for Home Assistant."""

import logging
import datetime
import pytz

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

        self._name = f"TI - {location['location_name']}"
        self._location_id = location["location_id"]
        self._unique_id = f"ti_{self._location_id}"
        self._state = None
        self._icon = icon
        self._device_identifier = device_identifier
        self.coordinator = coordinator
        self._location = location

        self.attrs = {}

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
    def extra_state_attributes(self):
        """Return the attributes."""
        telephone = self._location["location_telephone"].replace("-","")
        telephone = telephone.replace(" ","")
        telephone = telephone.replace("(","")
        telephone = telephone.replace(")","")
        if len(telephone) == 10:
            telephone = f"+1{telephone}"
        else:
            telephone = ""

        escalation_phone = str(self._location.get('location_escalation_phone')).replace("-","")
        escalation_phone = escalation_phone.replace(" ","")
        escalation_phone = escalation_phone.replace("(","")
        escalation_phone = escalation_phone.replace(")","")
        if len(escalation_phone) == 10:
            escalation_phone = f"+1{escalation_phone}"
        else:
            escalation_phone = ""

        self.attrs["phone"] = telephone
        self.attrs["escalation_phone"] = escalation_phone

        open_hours = self._location["options"].get("hours",{}).get("opening",{}).get("flexible",[])
        is_open = False
    
        today_details = {}
        for hours_detail in open_hours:
            if (hours_detail["day"] == str(datetime.datetime.today().weekday())):
                today_details = hours_detail
        
        if (today_details.get("status","0") == "1"):
            hours = today_details.get("hours","")
            open_hour = datetime.datetime.strptime(today_details.get("open","00:00"),"%H:%M").time()
            close_hour = datetime.datetime.strptime(today_details.get("close","00:00"),"%H:%M").time()
            current_time = datetime.datetime.now(pytz.timezone("America/Toronto")).time()

            if (hours != ""):
                hours_list = hours.split(",")
                if (len(hours_list) > 0):
                    for hours in hours_list:
                        today_hours = hours.split("-")
                        open_hour = datetime.datetime.strptime(today_hours[0],"%H:%M").time()
                        close_hour = datetime.datetime.strptime(today_hours[1],"%H:%M").time()
                        if (open_hour < close_hour):
                            if (current_time >= open_hour and current_time <= close_hour):
                                is_open=True
                        else:
                            if not (current_time >= close_hour and current_time <= open_hour):
                                is_open=True
            else:
                if (open_hour < close_hour):
                    if (current_time >= open_hour and current_time <= close_hour):
                        is_open=True
                else:
                    if not (current_time >= close_hour and current_time <= open_hour):
                        is_open=True

        self.attrs["is_open"] = is_open

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
