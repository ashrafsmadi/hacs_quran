"""Shared entity base for the single Quran Player device."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import ATTRIBUTION, DOMAIN, NAME, SIGNAL_STATE_UPDATED, VERSION
from .controller import QuranPlayerController


class QuranPlayerEntity(Entity):
    """Attach every Quran Player entity to the same service device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_attribution = ATTRIBUTION

    def __init__(self, controller: QuranPlayerController, key: str) -> None:
        """Initialize a controller-backed entity."""
        self.controller = controller
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.entry.entry_id)},
            name=NAME,
            manufacturer="Quran Player",
            model="Multi-room Quran audio controller",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://github.com/ashrafsmadi/hacs_quran",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to in-memory controller updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_STATE_UPDATED}_{self.controller.entry.entry_id}",
                self._handle_controller_update,
            )
        )

    @callback
    def _handle_controller_update(self) -> None:
        """Write cached controller state without doing I/O in properties."""
        self.async_write_ha_state()
