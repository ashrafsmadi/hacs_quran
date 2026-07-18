"""Playback-duration control for the one Quran Player device."""

from __future__ import annotations

from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QuranPlayerConfigEntry
from .controller import QuranPlayerController
from .entity import QuranPlayerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuranPlayerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sleep/playback duration number to the same device."""
    async_add_entities([QuranPlaybackDurationNumber(entry.runtime_data)])


class QuranPlaybackDurationNumber(QuranPlayerEntity, NumberEntity):
    """Stop playback after a wall-clock duration; zero means no limit."""

    _attr_translation_key = "playback_duration"
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 720
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, controller: QuranPlayerController) -> None:
        """Initialize playback duration control."""
        super().__init__(controller, "playback_duration")

    @property
    @override
    def native_value(self) -> int:
        """Return the configured duration, not a live countdown."""
        return self.controller.playback_duration

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set duration in whole minutes and restart an active sleep timer."""
        await self.controller.async_set_playback_duration(round(value))
