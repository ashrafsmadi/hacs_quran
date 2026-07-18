"""Quran Player integration setup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import PLATFORMS, STORAGE_KEY_PREFIX, STORAGE_VERSION
from .controller import QuranPlayerController

type QuranPlayerConfigEntry = ConfigEntry[QuranPlayerController]


async def async_setup_entry(hass: HomeAssistant, entry: QuranPlayerConfigEntry) -> bool:
    """Set up Quran Player from a UI config entry."""
    controller = QuranPlayerController(hass, entry)
    await controller.async_initialize()
    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: QuranPlayerConfigEntry
) -> bool:
    """Unload Quran Player and release all listeners and timers."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_shutdown()
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: QuranPlayerConfigEntry
) -> None:
    """Remove persisted selections when the config entry is deleted."""
    store: Store[dict[str, object]] = Store(
        hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
    )
    await store.async_remove()
