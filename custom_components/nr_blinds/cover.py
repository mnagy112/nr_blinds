"""Support for Motionblinds using their WLAN API."""

from __future__ import annotations

import logging
from typing import Any

from motionblinds import DEVICE_TYPES_WIFI, BlindType
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_ABSOLUTE_POSITION,
    ATTR_AVAILABLE,
    ATTR_WIDTH,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GATEWAY,
    SERVICE_SET_ABSOLUTE_POSITION,
    UPDATE_DELAY_STOP,
    UPDATE_INTERVAL_MOVING,
    UPDATE_INTERVAL_MOVING_WIFI,
)
from .entity import MotionCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


POSITION_DEVICE_MAP = {
    BlindType.RollerBlind: CoverDeviceClass.SHADE,
    BlindType.RomanBlind: CoverDeviceClass.SHADE,
    BlindType.HoneycombBlind: CoverDeviceClass.SHADE,
    BlindType.DimmingBlind: CoverDeviceClass.SHADE,
    BlindType.DayNightBlind: CoverDeviceClass.SHADE,
    BlindType.RollerShutter: CoverDeviceClass.SHUTTER,
    BlindType.Switch: CoverDeviceClass.SHUTTER,
    BlindType.RollerGate: CoverDeviceClass.GATE,
    BlindType.Awning: CoverDeviceClass.AWNING,
    BlindType.Curtain: CoverDeviceClass.CURTAIN,
    BlindType.CurtainLeft: CoverDeviceClass.CURTAIN,
    BlindType.CurtainRight: CoverDeviceClass.CURTAIN,
    BlindType.SkylightBlind: CoverDeviceClass.SHADE,
    BlindType.InsectScreen: CoverDeviceClass.SHADE,
}

TILT_DEVICE_MAP = {
    BlindType.VenetianBlind: CoverDeviceClass.BLIND,
    BlindType.ShangriLaBlind: CoverDeviceClass.BLIND,
    BlindType.DoubleRoller: CoverDeviceClass.SHADE,
    BlindType.DualShade: CoverDeviceClass.SHADE,
    BlindType.VerticalBlind: CoverDeviceClass.BLIND,
    BlindType.VerticalBlindLeft: CoverDeviceClass.BLIND,
    BlindType.VerticalBlindRight: CoverDeviceClass.BLIND,
}

# TILT_ONLY_DEVICE_MAP = {
#     BlindType.WoodShutter: CoverDeviceClass.BLIND,
# }

# TDBU_DEVICE_MAP = {
#     BlindType.TopDownBottomUp: CoverDeviceClass.SHADE,
#     BlindType.TriangleBlind: CoverDeviceClass.BLIND,
# }


# SET_ABSOLUTE_POSITION_SCHEMA: VolDictType = {
#     vol.Required(ATTR_ABSOLUTE_POSITION): vol.All(cv.positive_int, vol.Range(max=100)),
#     vol.Optional(ATTR_TILT_POSITION): vol.All(cv.positive_int, vol.Range(max=100)),
#     vol.Optional(ATTR_WIDTH): vol.All(cv.positive_int, vol.Range(max=100)),
# }


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Motion Blind from a config entry."""
    entities: list[MotionBaseDevice] = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        if blind.type in POSITION_DEVICE_MAP:
            entities.append(
                MotionPositionDevice(
                    coordinator,
                    blind,
                    POSITION_DEVICE_MAP[blind.type],
                )
            )

        elif blind.type in TILT_DEVICE_MAP:
            entities.append(
                MotionTiltDevice(
                    coordinator,
                    blind,
                    TILT_DEVICE_MAP[blind.type],
                )
            )

        else:
            _LOGGER.warning(
                "Blind type '%s' not yet supported, assuming RollerBlind",
                blind.blind_type,
            )
            entities.append(
                MotionPositionDevice(
                    coordinator,
                    blind,
                    POSITION_DEVICE_MAP[BlindType.RollerBlind],
                )
            )

    async_add_entities(entities)

    # platform = entity_platform.async_get_current_platform()
    # platform.async_register_entity_service(
    #     SERVICE_SET_ABSOLUTE_POSITION,
    #     SET_ABSOLUTE_POSITION_SCHEMA,
    #     "async_set_absolute_position",
    # )


class MotionBaseDevice(MotionCoordinatorEntity, CoverEntity):
    """Representation of a Motionblinds Device."""

    _restore_tilt = False

    def __init__(self, coordinator, blind, device_class):
        """Initialize the blind."""
        super().__init__(coordinator, blind)

        self._requesting_position: CALLBACK_TYPE | None = None
        self._previous_positions = []

        if blind.device_type in DEVICE_TYPES_WIFI:
            self._update_interval_moving = UPDATE_INTERVAL_MOVING_WIFI
        else:
            self._update_interval_moving = UPDATE_INTERVAL_MOVING

        self._attr_device_class = device_class
        self._attr_unique_id = blind.mac

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.coordinator.data is None:
            return False

        if not self.coordinator.data[KEY_GATEWAY][ATTR_AVAILABLE]:
            return False

        return self.coordinator.data[self._blind.mac][ATTR_AVAILABLE]

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.position is None:
            return None
        return 100 - self._blind.position

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None
        return self._blind.position == 100

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Open)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Close)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Stop)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Jog_up)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Jog_down)


class MotionPositionDevice(MotionBaseDevice):
    """Representation of a Motion Blind Device."""

    _attr_name = None


class MotionTiltDevice(MotionPositionDevice):
    """Representation of a Motionblinds Device."""

    _restore_tilt = False

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current angle of cover.

        None is unknown, 0 is closed/minimum tilt, 100 is fully open/maximum tilt.
        """
        if self._blind.angle is None:
            return None
        return self._blind.angle * 100 / 180

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None
        return self._blind.position >= 95
