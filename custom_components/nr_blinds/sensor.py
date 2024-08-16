"""Support for Motionblinds sensors."""

from motionblinds import DEVICE_TYPES_WIFI
from motionblinds.motion_blinds import DEVICE_TYPE_TDBU

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY
from .entity import MotionCoordinatorEntity

ATTR_BATTERY_VOLTAGE = "battery_voltage"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Motionblinds."""
    entities: list[SensorEntity] = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        entities.append(MotionSignalStrengthSensor(coordinator, blind))

    # Do not add signal sensor twice for direct WiFi blinds
    if motion_gateway.device_type not in DEVICE_TYPES_WIFI:
        entities.append(MotionSignalStrengthSensor(coordinator, motion_gateway))

    async_add_entities(entities)


class MotionSignalStrengthSensor(MotionCoordinatorEntity, SensorEntity):
    """Representation of a Motion Signal Strength Sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, blind):
        """Initialize the Motion Signal Strength Sensor."""
        super().__init__(coordinator, blind)
        self._attr_unique_id = f"{blind.mac}-RSSI"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._blind.RSSI
