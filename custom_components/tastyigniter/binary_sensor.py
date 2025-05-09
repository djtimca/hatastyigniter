"""Definition and setup of the TastyIgniter Binary Sensors for Home Assistant."""

import logging
import datetime
from homeassistant.util import dt

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
                hass,
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
        hass,
        coordinator: TastyIgniterCoordinator, 
        location: dict,
        icon: str,
        device_identifier: str,
        ):
        """Initialize Entities."""

        self.hass = hass
        self._name = f"TI - {location['location_name']}"
        self._location_id = location["location_id"]
        self._unique_id = f"ti_{self._location_id}"
        self._state = None
        self._icon = icon
        self._device_identifier = device_identifier
        self.coordinator = coordinator
        self._location = location
        self._last_update_time = None
        self._cached_is_open = False
        self._cached_attrs = {}
        
        # Pre-process static attributes that don't change frequently
        self._process_phone_attributes()

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

    def _process_phone_attributes(self):
        """Process phone numbers once during initialization."""
        # Process telephone
        telephone = self._location["location_telephone"].replace("-","")
        telephone = telephone.replace(" ","")
        telephone = telephone.replace("(","")
        telephone = telephone.replace(")","")
        if len(telephone) == 10:
            telephone = f"+1{telephone}"
        else:
            telephone = ""
            
        # Process escalation phone
        escalation_phone = str(self._location.get('location_escalation_phone', "")).replace("-","")
        escalation_phone = escalation_phone.replace(" ","")
        escalation_phone = escalation_phone.replace("(","")
        escalation_phone = escalation_phone.replace(")","")
        if len(escalation_phone) == 10:
            escalation_phone = f"+1{escalation_phone}"
        else:
            escalation_phone = ""
            
        # Store in cached attributes
        self._cached_attrs["phone"] = telephone
        self._cached_attrs["telephone_extension"] = self._location.get('telephone_extension')
        self._cached_attrs["escalation_phone"] = escalation_phone
    
    def _check_if_open(self):
        """Check if the location is currently open."""
        # Only recalculate every 5 minutes to improve performance
        # Get the timezone object from the string using dt.get_time_zone
        tz = dt.get_time_zone(self.hass.config.time_zone)
        current_time = dt.now(tz)
        
        # If we've checked in the last 5 minutes, return cached result
        if (self._last_update_time is not None and 
            (current_time - self._last_update_time).total_seconds() < 300):
            return self._cached_is_open
            
        # Update the last check time
        self._last_update_time = current_time
        is_open = False
        
        # Only check if location is active
        if self._location["location_status"] == True:
            open_hours = self._location["options"].get("hours",{}).get("opening",{}).get("flexible",[])
            today_details = {}
            
            # Find today's hours
            weekday = str(current_time.weekday())
            for hours_detail in open_hours:
                if hours_detail["day"] == weekday:
                    today_details = hours_detail
                    break
            
            # Check if open today
            if today_details.get("status","0") == "1":
                current_time = current_time.time()
                hours = today_details.get("hours","")
                
                if hours:
                    # Multiple time ranges
                    hours_list = hours.split(",")
                    for hour_range in hours_list:
                        today_hours = hour_range.split("-")
                        if len(today_hours) == 2:
                            open_hour = datetime.datetime.strptime(today_hours[0],"%H:%M").time()
                            close_hour = datetime.datetime.strptime(today_hours[1],"%H:%M").time()
                            
                            if open_hour < close_hour:
                                if current_time >= open_hour and current_time <= close_hour:
                                    is_open = True
                                    break
                            else:  # Handles overnight hours (e.g., 22:00-02:00)
                                if not (current_time >= close_hour and current_time <= open_hour):
                                    is_open = True
                                    break
                else:
                    # Single time range from open/close fields
                    open_hour = datetime.datetime.strptime(today_details.get("open","00:00"),"%H:%M").time()
                    close_hour = datetime.datetime.strptime(today_details.get("close","00:00"),"%H:%M").time()
                    
                    if open_hour < close_hour:
                        if current_time >= open_hour and current_time <= close_hour:
                            is_open = True
                    else:  # Handles overnight hours
                        if not (current_time >= close_hour and current_time <= open_hour):
                            is_open = True
        
        # Cache the result
        self._cached_is_open = is_open
        return is_open
    
    @property
    def extra_state_attributes(self):
        """Return the attributes."""
        # Start with the cached static attributes
        attributes = dict(self._cached_attrs)
        
        # Add the dynamic is_open attribute
        attributes["is_open"] = self._check_if_open()
        
        return attributes

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
