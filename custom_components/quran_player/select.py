"""Reciter, surah, and output selectors for the one Quran Player device."""

from __future__ import annotations

from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QuranPlayerConfigEntry
from .catalog import RECITERS, CatalogError, get_surah
from .controller import QuranPlayerController
from .entity import QuranPlayerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuranPlayerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add all selectors to the same Quran Player device."""
    controller = entry.runtime_data
    async_add_entities(
        [
            QuranReciterSelect(controller),
            QuranSurahSelect(controller),
            QuranOutputSelect(controller),
        ]
    )


class QuranReciterSelect(QuranPlayerEntity, SelectEntity):
    """Choose one of the eight owner-approved reciters."""

    _attr_translation_key = "reciter"

    def __init__(self, controller: QuranPlayerController) -> None:
        """Initialize the reciter selector."""
        super().__init__(controller, "reciter")

    @property
    @override
    def options(self) -> list[str]:
        """Return bilingual reciter labels."""
        return [reciter.display_name for reciter in RECITERS]

    @property
    @override
    def current_option(self) -> str:
        """Return the current bilingual reciter label."""
        return self.controller.reciter.display_name

    @override
    async def async_select_option(self, option: str) -> None:
        """Select a reciter by its current label."""
        match = next((item for item in RECITERS if item.display_name == option), None)
        if match is None:
            raise HomeAssistantError(
                translation_domain="quran_player", translation_key="invalid_reciter"
            )
        await self.controller.async_select_reciter(match.key, self._context)


class QuranSurahSelect(QuranPlayerEntity, SelectEntity):
    """Choose only a surah verified for the selected reciter."""

    _attr_translation_key = "surah"

    def __init__(self, controller: QuranPlayerController) -> None:
        """Initialize the surah selector."""
        super().__init__(controller, "surah")

    @property
    @override
    def options(self) -> list[str]:
        """Return available bilingual surah labels."""
        return [
            get_surah(number).display_name
            for number in self.controller.reciter.available_surahs
        ]

    @property
    @override
    def current_option(self) -> str:
        """Return the current bilingual surah label."""
        return self.controller.surah.display_name

    @override
    async def async_select_option(self, option: str) -> None:
        """Select an available surah by its current label."""
        match = next(
            (
                number
                for number in self.controller.reciter.available_surahs
                if get_surah(number).display_name == option
            ),
            None,
        )
        if match is None:
            raise HomeAssistantError(
                translation_domain="quran_player", translation_key="invalid_surah"
            )
        try:
            await self.controller.async_select_surah(match, self._context)
        except CatalogError as err:
            raise HomeAssistantError(
                translation_domain="quran_player",
                translation_key="invalid_surah",
            ) from err


class QuranOutputSelect(QuranPlayerEntity, SelectEntity):
    """Choose one configured output or all configured outputs."""

    _attr_translation_key = "output"

    def __init__(self, controller: QuranPlayerController) -> None:
        """Initialize the output selector."""
        super().__init__(controller, "output")

    @property
    @override
    def options(self) -> list[str]:
        """Return current friendly target labels."""
        return self.controller.target_options

    @property
    @override
    def current_option(self) -> str:
        """Return the selected target label."""
        return self.controller.selected_target_label

    @override
    async def async_select_option(self, option: str) -> None:
        """Select one target or all targets."""
        await self.controller.async_select_target(
            self.controller.target_from_label(option), self._context
        )
