"""Virtual media player that controls one or more existing HA outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, override

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QuranPlayerConfigEntry
from .catalog import (
    RECITERS,
    CatalogError,
    get_reciter,
    get_surah,
    parse_media_id,
)
from .catalog import (
    media_id as build_media_id,
)
from .const import MEDIA_ID_PREFIX, NAME
from .controller import QuranPlayerController
from .entity import QuranPlayerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuranPlayerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the one aggregate Quran media-player entity."""
    async_add_entities([QuranMediaPlayer(entry.runtime_data)])


class QuranMediaPlayer(QuranPlayerEntity, MediaPlayerEntity):
    """Represent the main feature of the single Quran Player device."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_icon = "mdi:book-open-page-variant"
    _attr_volume_step = 0.05
    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
    )

    def __init__(self, controller: QuranPlayerController) -> None:
        """Initialize the aggregate player."""
        super().__init__(controller, "player")

    @property
    @override
    def available(self) -> bool:
        """Remain controllable while individual outputs reconnect."""
        return bool(self.controller.targets)

    @property
    @override
    def state(self) -> MediaPlayerState:
        """Return cached virtual playback state."""
        return self.controller.state

    @property
    @override
    def media_content_id(self) -> str:
        """Return a safe internal identifier rather than the third-party URL."""
        return build_media_id(self.controller.reciter_key, self.controller.surah_number)

    @property
    @override
    def media_content_type(self) -> MediaType:
        """Return the Home Assistant media classification."""
        return MediaType.MUSIC

    @property
    @override
    def media_title(self) -> str:
        """Return the bilingual selected surah title."""
        return self.controller.surah.display_name

    @property
    @override
    def media_artist(self) -> str:
        """Return the bilingual selected reciter name."""
        return self.controller.reciter.display_name

    @property
    @override
    def media_track(self) -> int:
        """Return the surah number."""
        return self.controller.surah_number

    @property
    @override
    def media_duration(self) -> float | None:
        """Mirror duration from the first ordered active target."""
        state = self.controller.target_state()
        raw = state.attributes.get("media_duration") if state is not None else None
        return float(raw) if isinstance(raw, (int, float)) else None

    @property
    @override
    def media_position(self) -> float | None:
        """Mirror position from the first ordered active target."""
        state = self.controller.target_state()
        raw = state.attributes.get("media_position") if state is not None else None
        return float(raw) if isinstance(raw, (int, float)) else None

    @property
    @override
    def media_position_updated_at(self) -> datetime | None:
        """Mirror position timestamp from the first ordered active target."""
        state = self.controller.target_state()
        raw = (
            state.attributes.get("media_position_updated_at")
            if state is not None
            else None
        )
        return raw if isinstance(raw, datetime) else None

    @property
    @override
    def volume_level(self) -> float:
        """Return selected output volume or an all-output average."""
        return self.controller.volume_level

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Return aggregate mute state when real targets report it."""
        return self.controller.is_volume_muted

    @property
    @override
    def source(self) -> str:
        """Return the selected output label."""
        return self.controller.selected_target_label

    @property
    @override
    def source_list(self) -> list[str]:
        """Expose one output or all configured outputs in the player card."""
        return self.controller.target_options

    @property
    @override
    def repeat(self) -> str:
        """Return standard Off, One, or All repeat state."""
        return self.controller.repeat_mode

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful, non-sensitive playback diagnostics."""
        return {
            "reciter_key": self.controller.reciter_key,
            "reciter_arabic": self.controller.reciter.arabic_name,
            "surah_number": self.controller.surah_number,
            "surah_arabic": self.controller.surah.arabic_name,
            "available_surahs": len(self.controller.reciter.available_surahs),
            "selected_target": self.controller.selected_target,
            "active_targets": list(self.controller.active_targets),
            "target_states": self.controller.target_debug_attributes(),
            "playback_duration_minutes": self.controller.playback_duration,
            "sleep_timer_ends_at": self.controller.sleep_timer_ends_at,
            "source_page": self.controller.reciter.source_url,
            "last_failed_targets": list(self.controller.last_failures),
        }

    @override
    async def async_media_play(self) -> None:
        """Start or resume playback."""
        await self.controller.async_play(self._context)

    @override
    async def async_media_pause(self) -> None:
        """Pause this integration's active outputs."""
        await self.controller.async_pause(self._context)

    @override
    async def async_media_stop(self) -> None:
        """Stop this integration's active outputs."""
        await self.controller.async_stop(self._context)

    @override
    async def async_media_next_track(self) -> None:
        """Move to the next verified available surah."""
        await self.controller.async_next(self._context)

    @override
    async def async_media_previous_track(self) -> None:
        """Move to the previous verified available surah."""
        await self.controller.async_previous(self._context)

    @override
    async def async_media_seek(self, position: float) -> None:
        """Seek every active output when the target integration supports it."""
        await self.controller.async_seek(position, self._context)

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set per-output or all-output volume."""
        await self.controller.async_set_volume(volume, self._context)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the active session or selected outputs."""
        await self.controller.async_mute(mute, self._context)

    @override
    async def async_select_source(self, source: str) -> None:
        """Select one configured output or all configured outputs."""
        await self.controller.async_select_target(
            self.controller.target_from_label(source), self._context
        )

    @override
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set standard repeat behavior."""
        await self.controller.async_set_repeat(repeat.value)

    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a Quran Player item chosen through HA's media browser."""
        try:
            reciter_key, surah_number = parse_media_id(media_id)
        except CatalogError as err:
            raise HomeAssistantError(
                translation_domain="quran_player",
                translation_key="invalid_media_id",
            ) from err
        await self.controller.async_select_media(
            reciter_key, surah_number, self._context
        )

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse the static hierarchy Reciter → available Surah."""
        requested_id = media_content_id or MEDIA_ID_PREFIX
        if requested_id == MEDIA_ID_PREFIX:
            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id=MEDIA_ID_PREFIX,
                media_content_type=MediaType.MUSIC,
                title=NAME,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.ARTIST,
                children=[
                    BrowseMedia(
                        media_class=MediaClass.ARTIST,
                        media_content_id=f"{MEDIA_ID_PREFIX}{reciter.key}",
                        media_content_type=MediaType.MUSIC,
                        title=reciter.display_name,
                        can_play=False,
                        can_expand=True,
                    )
                    for reciter in RECITERS
                ],
            )

        raw_path = requested_id.removeprefix(MEDIA_ID_PREFIX).strip("/")
        if "/" not in raw_path:
            try:
                reciter = get_reciter(raw_path)
            except CatalogError as err:
                raise HomeAssistantError(
                    translation_domain="quran_player",
                    translation_key="invalid_media_id",
                ) from err
            return BrowseMedia(
                media_class=MediaClass.ARTIST,
                media_content_id=requested_id,
                media_content_type=MediaType.MUSIC,
                title=reciter.display_name,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.TRACK,
                children=[
                    BrowseMedia(
                        media_class=MediaClass.TRACK,
                        media_content_id=build_media_id(reciter.key, number),
                        media_content_type=MediaType.MUSIC,
                        title=get_surah(number).display_name,
                        can_play=True,
                        can_expand=False,
                    )
                    for number in reciter.available_surahs
                ],
            )

        try:
            _reciter_key, surah_number = parse_media_id(requested_id)
        except CatalogError as err:
            raise HomeAssistantError(
                translation_domain="quran_player",
                translation_key="invalid_media_id",
            ) from err
        return BrowseMedia(
            media_class=MediaClass.TRACK,
            media_content_id=requested_id,
            media_content_type=MediaType.MUSIC,
            title=get_surah(surah_number).display_name,
            can_play=True,
            can_expand=False,
            children=None,
        )
