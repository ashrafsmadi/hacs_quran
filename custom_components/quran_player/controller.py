"""Playback coordinator for the Quran Player integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from typing import Any, Final

from homeassistant.components.media_player.const import MediaPlayerState, RepeatMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .catalog import RECITERS, CatalogError, Reciter, Surah, get_reciter, get_surah
from .const import (
    ALL_TARGETS,
    ALL_TARGETS_LABEL,
    CONF_DEFAULT_RECITER,
    CONF_DEFAULT_VOLUME,
    CONF_MEDIA_PLAYERS,
    DEFAULT_PLAYBACK_DURATION,
    DEFAULT_RECITER,
    DEFAULT_SURAH,
    DEFAULT_VOLUME,
    MEDIA_MIME_TYPE,
    SIGNAL_STATE_UPDATED,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

_FINISH_GRACE_SECONDS: Final = 2
_COMMAND_EVENT_GRACE_SECONDS: Final = 4
_TERMINAL_STATES: Final = {
    MediaPlayerState.IDLE,
    MediaPlayerState.OFF,
    MediaPlayerState.ON,
    MediaPlayerState.STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
}
_ACTIVE_STATES: Final = {MediaPlayerState.PLAYING, MediaPlayerState.BUFFERING}
_VALID_REPEAT_MODES: Final = {mode.value for mode in RepeatMode}


@dataclass(frozen=True, slots=True)
class FanoutResult:
    """Result of calling a Home Assistant media-player action per target."""

    succeeded: tuple[str, ...]
    failed: dict[str, str]


class QuranPlayerController:
    """Own selections and safely fan playback out to existing media players."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the controller from config-entry options."""
        self.hass = hass
        self.entry = entry
        self.targets = tuple(dict.fromkeys(entry.options.get(CONF_MEDIA_PLAYERS, ())))

        configured_reciter = entry.options.get(CONF_DEFAULT_RECITER, DEFAULT_RECITER)
        self.default_reciter_key = (
            configured_reciter
            if configured_reciter in {item.key for item in self.reciters}
            else DEFAULT_RECITER
        )
        raw_volume = float(entry.options.get(CONF_DEFAULT_VOLUME, DEFAULT_VOLUME * 100))
        self.default_volume = max(0.0, min(1.0, raw_volume / 100.0))

        self.reciter_key = self.default_reciter_key
        self.surah_number = DEFAULT_SURAH
        self.selected_target = ALL_TARGETS
        self.repeat_mode = RepeatMode.ALL.value
        self.playback_duration = DEFAULT_PLAYBACK_DURATION
        self.target_volumes: dict[str, float] = {}

        self.state = MediaPlayerState.IDLE
        self.active_targets: tuple[str, ...] = ()
        self.last_failures: dict[str, str] = {}
        self.sleep_timer_ends_at: datetime | None = None

        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )
        self._command_lock = asyncio.Lock()
        self._shutdown = False
        self._generation = 0
        self._sleep_token = 0
        self._ignore_finish_until = 0.0
        self._remove_target_listener: Callable[[], None] | None = None
        self._cancel_finish_confirmation: Callable[[], None] | None = None
        self._cancel_sleep_timer: Callable[[], None] | None = None

    @property
    def reciters(self) -> tuple[Reciter, ...]:
        """Return the static catalog without importing it at module initialization."""
        return RECITERS

    @property
    def reciter(self) -> Reciter:
        """Return the selected reciter."""
        return get_reciter(self.reciter_key)

    @property
    def surah(self) -> Surah:
        """Return the selected surah."""
        return get_surah(self.surah_number)

    @property
    def stream_url(self) -> str:
        """Return the selected direct MP3 URL."""
        return self.reciter.stream_url(self.surah_number)

    @property
    def is_session_active(self) -> bool:
        """Return whether this integration currently owns a playback session."""
        return bool(self.active_targets)

    async def async_initialize(self) -> None:
        """Restore safe selections and subscribe to target state changes."""
        restored = await self._store.async_load()
        if restored:
            self._restore(restored)

        if self.targets:
            self._remove_target_listener = async_track_state_change_event(
                self.hass, self.targets, self._handle_target_state_event
            )

        # Playback and timers intentionally never resume merely because HA restarted.
        self.state = MediaPlayerState.IDLE
        self.active_targets = ()
        self.sleep_timer_ends_at = None

    async def async_shutdown(self) -> None:
        """Stop an owned session, then remove listeners and timers."""
        async with self._command_lock:
            self._shutdown = True
            self._generation += 1
            self._cancel_pending_finish()
            self._cancel_sleep()
            targets = self.active_targets
            if targets:
                result = await self._async_fanout(
                    "media_stop", targets, skip_unavailable=False
                )
                if result.failed:
                    _LOGGER.error(
                        "Unable to stop Quran playback while unloading: %s",
                        ", ".join(result.failed),
                    )
            if self._remove_target_listener is not None:
                self._remove_target_listener()
                self._remove_target_listener = None
            self.active_targets = ()
            self.state = MediaPlayerState.IDLE

    def _ensure_running(self) -> None:
        """Reject commands once this controller has begun unloading."""
        if self._shutdown:
            raise HomeAssistantError(
                translation_domain="quran_player",
                translation_key="integration_unloading",
            )

    def _target_is_terminal(self, target: str) -> bool:
        """Return whether a real target is confirmed not to be playing."""
        state = self.hass.states.get(target)
        return state is not None and state.state in _TERMINAL_STATES

    def _restore(self, restored: dict[str, Any]) -> None:
        """Restore persisted selections with strict validation and safe fallbacks."""
        raw_reciter = restored.get("reciter")
        if isinstance(raw_reciter, str):
            with suppress(CatalogError):
                get_reciter(raw_reciter)
                self.reciter_key = raw_reciter

        raw_surah = restored.get("surah")
        if isinstance(raw_surah, int) and 1 <= raw_surah <= 114:
            self.surah_number = self.reciter.nearest_surah(raw_surah)
        else:
            self.surah_number = self.reciter.nearest_surah(DEFAULT_SURAH)

        raw_target = restored.get("target")
        if raw_target == ALL_TARGETS or raw_target in self.targets:
            self.selected_target = raw_target

        raw_repeat = restored.get("repeat")
        if raw_repeat in _VALID_REPEAT_MODES:
            self.repeat_mode = raw_repeat

        raw_duration = restored.get("duration")
        if isinstance(raw_duration, (int, float)) and 0 <= raw_duration <= 720:
            self.playback_duration = int(raw_duration)

        raw_volumes = restored.get("volumes")
        if isinstance(raw_volumes, dict):
            self.target_volumes = {
                target: max(0.0, min(1.0, float(volume)))
                for target, volume in raw_volumes.items()
                if target in self.targets and isinstance(volume, (int, float))
            }

    def _serialized_state(self) -> dict[str, Any]:
        """Return only persistent user choices, never transient playback state."""
        return {
            "reciter": self.reciter_key,
            "surah": self.surah_number,
            "target": self.selected_target,
            "repeat": self.repeat_mode,
            "duration": self.playback_duration,
            "volumes": self.target_volumes,
        }

    async def _async_save(self) -> None:
        """Persist current user choices."""
        await self._store.async_save(self._serialized_state())

    @callback
    def _notify(self) -> None:
        """Notify all entities attached to this one device."""
        async_dispatcher_send(
            self.hass, f"{SIGNAL_STATE_UPDATED}_{self.entry.entry_id}"
        )

    def target_label_map(self) -> dict[str, str]:
        """Return stable target IDs mapped to readable current labels."""
        labels = {ALL_TARGETS: ALL_TARGETS_LABEL}
        for entity_id in self.targets:
            state = self.hass.states.get(entity_id)
            friendly_name = (
                state.attributes.get(ATTR_FRIENDLY_NAME) if state is not None else None
            )
            labels[entity_id] = f"{friendly_name or entity_id} ({entity_id})"
        return labels

    @property
    def target_options(self) -> list[str]:
        """Return output selector labels."""
        return list(self.target_label_map().values())

    @property
    def selected_target_label(self) -> str:
        """Return the current output selector label."""
        return self.target_label_map().get(
            self.selected_target, self.target_label_map()[ALL_TARGETS]
        )

    def target_from_label(self, label: str) -> str:
        """Resolve a current output label to its stable target ID."""
        for target, current_label in self.target_label_map().items():
            if current_label == label:
                return target
        raise HomeAssistantError(
            translation_domain="quran_player", translation_key="invalid_target"
        )

    def selected_targets(self) -> tuple[str, ...]:
        """Return target IDs for the current one/all selection."""
        if self.selected_target == ALL_TARGETS:
            return self.targets
        if self.selected_target in self.targets:
            return (self.selected_target,)
        return self.targets

    def target_state(self, entity_id: str | None = None) -> State | None:
        """Return a deterministic real-player state for aggregate attributes."""
        if entity_id is not None:
            return self.hass.states.get(entity_id)
        candidates = self.active_targets or self.selected_targets()
        return self.hass.states.get(candidates[0]) if candidates else None

    @property
    def volume_level(self) -> float:
        """Return selected target volume or the average for all configured targets."""
        targets = self.selected_targets()
        if not targets:
            return self.default_volume
        volumes: list[float] = []
        for target in targets:
            state = self.hass.states.get(target)
            raw = state.attributes.get("volume_level") if state is not None else None
            if isinstance(raw, (int, float)):
                volumes.append(float(raw))
            else:
                volumes.append(self.target_volumes.get(target, self.default_volume))
        return sum(volumes) / len(volumes)

    @property
    def is_volume_muted(self) -> bool | None:
        """Return aggregate mute state, or None when no target reports it."""
        values: list[bool] = []
        for target in self.selected_targets():
            state = self.hass.states.get(target)
            raw = state.attributes.get("is_volume_muted") if state is not None else None
            if isinstance(raw, bool):
                values.append(raw)
        return all(values) if values else None

    async def _async_fanout(
        self,
        service: str,
        targets: Iterable[str],
        data: dict[str, Any] | None = None,
        *,
        context: Context | None = None,
        skip_unavailable: bool = True,
    ) -> FanoutResult:
        """Call a media-player action independently so one failure cannot block all."""
        ordered_targets = tuple(dict.fromkeys(targets))

        async def _call(target: str) -> tuple[str, Exception | None]:
            current = self.hass.states.get(target)
            if skip_unavailable and (
                current is None or current.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}
            ):
                return target, HomeAssistantError(
                    translation_domain="quran_player",
                    translation_key="target_unavailable",
                    translation_placeholders={"target": target},
                )
            try:
                await self.hass.services.async_call(
                    "media_player",
                    service,
                    data or {},
                    blocking=True,
                    context=context,
                    target={ATTR_ENTITY_ID: target},
                )
            except Exception as err:  # Home Assistant service errors are target-local.
                return target, err
            return target, None

        results = await asyncio.gather(*(_call(target) for target in ordered_targets))
        succeeded = tuple(target for target, error in results if error is None)
        failed = {
            target: str(error) or error.__class__.__name__
            for target, error in results
            if error is not None
        }
        if failed:
            _LOGGER.warning(
                "Quran Player action %s failed for: %s",
                service,
                ", ".join(failed),
            )
        self.last_failures = failed
        return FanoutResult(succeeded=succeeded, failed=failed)

    async def _async_apply_volumes(
        self, targets: Iterable[str], context: Context | None
    ) -> None:
        """Apply each target's remembered volume before starting playback."""
        await asyncio.gather(
            *(
                self._async_fanout(
                    "volume_set",
                    (target,),
                    {
                        "volume_level": self.target_volumes.get(
                            target, self.default_volume
                        )
                    },
                    context=context,
                )
                for target in targets
            )
        )

    async def async_play(self, context: Context | None = None) -> None:
        """Start or resume the selected recitation."""
        async with self._command_lock:
            self._ensure_running()
            if self.state == MediaPlayerState.PAUSED and self.active_targets:
                targets = self.active_targets
                result = await self._async_fanout(
                    "media_play", targets, context=context
                )
                if not result.succeeded:
                    raise self._targets_failed("resume_failed", result)
                # Retain session ownership even when a target failed to resume; it
                # may still be paused and must remain stoppable by this integration.
                self.active_targets = targets
                self.state = MediaPlayerState.PLAYING
                self._generation += 1
                self._ignore_finish_until = monotonic() + _COMMAND_EVENT_GRACE_SECONDS
                self._notify()
                return
            await self._async_play_selected_locked(context, reset_sleep_timer=True)

    async def _async_play_selected_locked(
        self, context: Context | None, *, reset_sleep_timer: bool
    ) -> None:
        """Start the selected stream; caller must hold the command lock."""
        self._ensure_running()
        targets = self.selected_targets()
        if not targets:
            raise HomeAssistantError(
                translation_domain="quran_player", translation_key="no_targets"
            )

        previous_active = self.active_targets
        previous_state = self.state
        self._generation += 1
        self._cancel_pending_finish()
        self._ignore_finish_until = monotonic() + _COMMAND_EVENT_GRACE_SECONDS
        await self._async_apply_volumes(targets, context)

        result = await self._async_fanout(
            "play_media",
            targets,
            {
                "media_content_id": self.stream_url,
                "media_content_type": MEDIA_MIME_TYPE,
            },
            context=context,
        )
        retained_targets = tuple(
            target
            for target in previous_active
            if target in result.failed and not self._target_is_terminal(target)
        )
        if not result.succeeded:
            self.active_targets = retained_targets
            if retained_targets:
                self.state = previous_state
            else:
                self.state = MediaPlayerState.IDLE
                self._cancel_sleep()
            self._notify()
            raise self._targets_failed("play_failed", result)

        owned_targets = set(result.succeeded) | set(retained_targets)
        self.active_targets = tuple(
            target
            for target in dict.fromkeys((*targets, *previous_active))
            if target in owned_targets
        )
        self.state = MediaPlayerState.PLAYING
        if reset_sleep_timer:
            self._schedule_sleep()
        self._notify()
        await self._async_save()

    def _targets_failed(
        self, translation_key: str, result: FanoutResult
    ) -> HomeAssistantError:
        """Build an action-specific translated target-failure error."""
        return HomeAssistantError(
            translation_domain="quran_player",
            translation_key=translation_key,
            translation_placeholders={
                "targets": ", ".join(result.failed) or "none",
            },
        )

    async def async_pause(self, context: Context | None = None) -> None:
        """Pause only speakers participating in this Quran session."""
        async with self._command_lock:
            self._ensure_running()
            if not self.active_targets:
                return
            targets = self.active_targets
            previous_state = self.state
            self._generation += 1
            self._cancel_pending_finish()
            self._ignore_finish_until = monotonic() + _COMMAND_EVENT_GRACE_SECONDS
            result = await self._async_fanout("media_pause", targets, context=context)
            if not result.succeeded:
                raise self._targets_failed("pause_failed", result)
            # Failed targets may still be playing, so keep ownership of the entire
            # session. Only claim an aggregate paused state after every call works.
            self.active_targets = targets
            self.state = (
                MediaPlayerState.PAUSED if not result.failed else previous_state
            )
            self._notify()

    async def async_stop(self, context: Context | None = None) -> None:
        """Stop only speakers participating in this Quran session."""
        async with self._command_lock:
            self._ensure_running()
            result = await self._async_stop_locked(context, cancel_sleep=True)
            if result.failed:
                raise self._targets_failed("stop_failed", result)

    async def _async_stop_locked(
        self, context: Context | None, *, cancel_sleep: bool
    ) -> FanoutResult:
        """Stop active targets; caller must hold the command lock."""
        self._generation += 1
        self._cancel_pending_finish()
        if cancel_sleep:
            self._cancel_sleep()
        targets = self.active_targets
        previous_state = self.state
        self._ignore_finish_until = monotonic() + _COMMAND_EVENT_GRACE_SECONDS
        if not targets:
            self.state = MediaPlayerState.IDLE
            self._notify()
            return FanoutResult(succeeded=(), failed={})

        result = await self._async_fanout(
            "media_stop", targets, context=context, skip_unavailable=False
        )
        remaining_failures = {
            target: error
            for target, error in result.failed.items()
            if not self._target_is_terminal(target)
        }
        self.active_targets = tuple(
            target for target in targets if target in remaining_failures
        )
        self.state = previous_state if self.active_targets else MediaPlayerState.IDLE
        confirmed = tuple(
            target for target in targets if target not in remaining_failures
        )
        settled_result = FanoutResult(
            succeeded=confirmed,
            failed=remaining_failures,
        )
        self.last_failures = remaining_failures
        self._notify()
        return settled_result

    async def async_set_volume(
        self, volume: float, context: Context | None = None
    ) -> None:
        """Set and remember volume for the selected speaker or all speakers."""
        if not 0.0 <= volume <= 1.0:
            raise HomeAssistantError(
                translation_domain="quran_player", translation_key="invalid_volume"
            )
        async with self._command_lock:
            self._ensure_running()
            targets = self.selected_targets()
            result = await self._async_fanout(
                "volume_set",
                targets,
                {"volume_level": volume},
                context=context,
            )
            if not result.succeeded:
                raise self._targets_failed("volume_failed", result)
            for target in result.succeeded:
                self.target_volumes[target] = volume
            self._notify()
            await self._async_save()

    async def async_mute(self, mute: bool, context: Context | None = None) -> None:
        """Mute the active session or current selection."""
        async with self._command_lock:
            self._ensure_running()
            targets = self.active_targets or self.selected_targets()
            result = await self._async_fanout(
                "volume_mute", targets, {"is_volume_muted": mute}, context=context
            )
            if not result.succeeded:
                raise self._targets_failed("mute_failed", result)
            self._notify()

    async def async_seek(self, position: float, context: Context | None = None) -> None:
        """Seek all active session targets to a playback position in seconds."""
        if position < 0:
            raise HomeAssistantError(
                translation_domain="quran_player", translation_key="invalid_position"
            )
        async with self._command_lock:
            self._ensure_running()
            if not self.active_targets:
                raise HomeAssistantError(
                    translation_domain="quran_player",
                    translation_key="no_active_session",
                )
            result = await self._async_fanout(
                "media_seek",
                self.active_targets,
                {"seek_position": position},
                context=context,
            )
            if not result.succeeded:
                raise self._targets_failed("seek_failed", result)

    async def async_next(self, context: Context | None = None) -> None:
        """Select the next available surah and restart if currently active."""
        await self._async_move(1, context)

    async def async_previous(self, context: Context | None = None) -> None:
        """Select the previous available surah and restart if currently active."""
        await self._async_move(-1, context)

    async def _async_move(self, step: int, context: Context | None) -> None:
        """Move within the selected reciter's verified available-surah list."""
        async with self._command_lock:
            self._ensure_running()
            self.surah_number = self.reciter.adjacent_surah(self.surah_number, step)
            if self.active_targets:
                await self._async_play_selected_locked(context, reset_sleep_timer=False)
            else:
                self._notify()
                await self._async_save()

    async def async_select_reciter(
        self, reciter_key: str, context: Context | None = None
    ) -> None:
        """Select a reviewed reciter and move to a valid surah if needed."""
        try:
            reciter = get_reciter(reciter_key)
        except CatalogError as err:
            raise HomeAssistantError(
                translation_domain="quran_player",
                translation_key="invalid_reciter",
            ) from err
        async with self._command_lock:
            self._ensure_running()
            self.reciter_key = reciter.key
            self.surah_number = reciter.nearest_surah(self.surah_number)
            if self.active_targets:
                await self._async_play_selected_locked(context, reset_sleep_timer=False)
            else:
                self._notify()
                await self._async_save()

    async def async_select_surah(
        self, surah_number: int, context: Context | None = None
    ) -> None:
        """Select an available surah and restart if currently active."""
        async with self._command_lock:
            self._ensure_running()
            try:
                self.reciter.stream_url(surah_number)
            except CatalogError as err:
                raise HomeAssistantError(
                    translation_domain="quran_player",
                    translation_key="invalid_surah",
                ) from err
            self.surah_number = surah_number
            if self.active_targets:
                await self._async_play_selected_locked(context, reset_sleep_timer=False)
            else:
                self._notify()
                await self._async_save()

    async def async_select_media(
        self,
        reciter_key: str,
        surah_number: int,
        context: Context | None = None,
    ) -> None:
        """Atomically select a browsed reciter/surah and play it once."""
        try:
            reciter = get_reciter(reciter_key)
            reciter.stream_url(surah_number)
        except CatalogError as err:
            raise HomeAssistantError(
                translation_domain="quran_player",
                translation_key="invalid_media_id",
            ) from err
        async with self._command_lock:
            self._ensure_running()
            self.reciter_key = reciter.key
            self.surah_number = surah_number
            await self._async_play_selected_locked(
                context, reset_sleep_timer=not self.active_targets
            )

    async def async_select_target(
        self, target: str, context: Context | None = None
    ) -> None:
        """Select one output or all outputs, moving an active session safely."""
        async with self._command_lock:
            self._ensure_running()
            if target != ALL_TARGETS and target not in self.targets:
                raise HomeAssistantError(
                    translation_domain="quran_player",
                    translation_key="invalid_target",
                )
            was_active = bool(self.active_targets)
            if was_active:
                result = await self._async_stop_locked(context, cancel_sleep=False)
                if result.failed:
                    raise self._targets_failed("stop_failed", result)
            self.selected_target = target
            if was_active:
                await self._async_play_selected_locked(context, reset_sleep_timer=False)
            else:
                self._notify()
                await self._async_save()

    async def async_set_repeat(self, repeat: str) -> None:
        """Set Home Assistant's standard repeat mode."""
        if repeat not in _VALID_REPEAT_MODES:
            raise HomeAssistantError(
                translation_domain="quran_player", translation_key="invalid_repeat"
            )
        async with self._command_lock:
            self._ensure_running()
            self.repeat_mode = repeat
            self._notify()
            await self._async_save()

    async def async_set_playback_duration(self, minutes: int) -> None:
        """Set the wall-clock sleep timer in minutes; zero disables it."""
        if not 0 <= minutes <= 720:
            raise HomeAssistantError(
                translation_domain="quran_player", translation_key="invalid_duration"
            )
        async with self._command_lock:
            self._ensure_running()
            self.playback_duration = minutes
            if self.active_targets:
                self._schedule_sleep()
            else:
                self._cancel_sleep()
            self._notify()
            await self._async_save()

    def _schedule_sleep(self) -> None:
        """Replace the sleep timer using elapsed wall-clock time."""
        self._cancel_sleep()
        if self.playback_duration <= 0 or not self.active_targets:
            return
        delay = timedelta(minutes=self.playback_duration)
        self.sleep_timer_ends_at = dt_util.utcnow() + delay
        sleep_token = self._sleep_token

        @callback
        def _timer_finished(_now: datetime) -> None:
            self._cancel_sleep_timer = None
            self.sleep_timer_ends_at = None
            self.hass.async_create_task(
                self._async_sleep_finished(sleep_token),
                f"{self.entry.title} sleep timer",
            )

        self._cancel_sleep_timer = async_call_later(
            self.hass, delay.total_seconds(), _timer_finished
        )

    async def _async_sleep_finished(self, sleep_token: int) -> None:
        """Stop the current session once when its timer expires."""
        async with self._command_lock:
            if sleep_token != self._sleep_token or not self.active_targets:
                return
            await self._async_stop_locked(None, cancel_sleep=True)

    def _cancel_sleep(self) -> None:
        """Cancel and clear the current sleep timer."""
        self._sleep_token += 1
        if self._cancel_sleep_timer is not None:
            self._cancel_sleep_timer()
            self._cancel_sleep_timer = None
        self.sleep_timer_ends_at = None

    @callback
    def _handle_target_state_event(self, event: Event[EventStateChangedData]) -> None:
        """Mirror active state and detect a genuine end-of-track transition."""
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        old_state = event.data["old_state"]
        if entity_id not in self.active_targets or new_state is None:
            self._notify()
            return

        if new_state.state in _ACTIVE_STATES:
            self.state = MediaPlayerState(new_state.state)
            self._cancel_pending_finish()
            self._notify()
            return

        if new_state.state == MediaPlayerState.PAUSED:
            if all(
                (state := self.hass.states.get(target)) is not None
                and state.state == MediaPlayerState.PAUSED
                for target in self.active_targets
            ):
                self.state = MediaPlayerState.PAUSED
            self._cancel_pending_finish()
            self._notify()
            return

        if (
            old_state is None
            or old_state.state not in _ACTIVE_STATES
            or new_state.state not in _TERMINAL_STATES
        ):
            self._notify()
            return

        if any(
            (state := self.hass.states.get(target)) is not None
            and state.state not in _TERMINAL_STATES
            for target in self.active_targets
        ):
            self._notify()
            return

        confirmation_delay = _FINISH_GRACE_SECONDS + max(
            0.0, self._ignore_finish_until - monotonic()
        )
        self._schedule_finish_confirmation(confirmation_delay)
        self._notify()

    @callback
    def _schedule_finish_confirmation(
        self, delay: float = _FINISH_GRACE_SECONDS
    ) -> None:
        """Debounce simultaneous completion events from multiple outputs."""
        if self._cancel_finish_confirmation is not None:
            return
        generation = self._generation

        @callback
        def _confirmed(_now: datetime) -> None:
            self._cancel_finish_confirmation = None
            self.hass.async_create_task(
                self._async_track_finished(generation),
                f"{self.entry.title} advance Quran track",
            )

        self._cancel_finish_confirmation = async_call_later(
            self.hass, delay, _confirmed
        )

    async def _async_track_finished(self, generation: int) -> None:
        """Apply repeat mode after all active outputs finish the same generation."""
        async with self._command_lock:
            if generation != self._generation or not self.active_targets:
                return
            if any(
                (state := self.hass.states.get(target)) is not None
                and state.state not in _TERMINAL_STATES
                for target in self.active_targets
            ):
                return

            if self.repeat_mode == RepeatMode.OFF:
                self.active_targets = ()
                self.state = MediaPlayerState.IDLE
                self._cancel_sleep()
                self._notify()
                return
            if self.repeat_mode == RepeatMode.ALL:
                self.surah_number = self.reciter.adjacent_surah(self.surah_number, 1)
            try:
                await self._async_play_selected_locked(None, reset_sleep_timer=False)
            except HomeAssistantError as err:
                _LOGGER.error("Unable to continue automatic Quran playback: %s", err)
                if not self.active_targets:
                    self.state = MediaPlayerState.IDLE
                    self._cancel_sleep()
                self._notify()

    def _cancel_pending_finish(self) -> None:
        """Cancel a debounced end-of-track action."""
        if self._cancel_finish_confirmation is not None:
            self._cancel_finish_confirmation()
            self._cancel_finish_confirmation = None

    def target_debug_attributes(self) -> dict[str, str]:
        """Return non-sensitive target states for player attributes and diagnostics."""
        return {
            target: state.state
            if (state := self.hass.states.get(target))
            else "missing"
            for target in self.targets
        }
