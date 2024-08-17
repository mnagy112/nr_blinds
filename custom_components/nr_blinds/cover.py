"""Support for Motionblinds using their WLAN API."""

from __future__ import annotations

import logging
from typing import Any

from motionblinds import DEVICE_TYPES_WIFI

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_AVAILABLE,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GATEWAY,
    UPDATE_INTERVAL_MOVING,
    UPDATE_INTERVAL_MOVING_WIFI,
)
from .entity import MotionCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Motion Blind from a config entry."""
    entities: list[VenetianBlindDevice] = []

    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        entities.append(
            VenetianBlindDevice(
                coordinator,
                blind,
                CoverDeviceClass.BLIND,
            )
        )

    async_add_entities(entities)


class VenetianBlindDevice(MotionCoordinatorEntity, CoverEntity):
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

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
        )

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

