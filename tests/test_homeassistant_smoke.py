"""HA-backed controller and entity contract tests."""

from __future__ import annotations

import asyncio
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import Context, State
from homeassistant.exceptions import HomeAssistantError

from custom_components.quran_player.const import (
    CONF_DEFAULT_RECITER,
    CONF_DEFAULT_VOLUME,
    CONF_MEDIA_PLAYERS,
)
from custom_components.quran_player.controller import (
    QuranPlayerController,
)
from custom_components.quran_player.media_player import QuranMediaPlayer


class _States:
    def __init__(self, entity_ids: list[str]) -> None:
        self.values = {
            entity_id: State(entity_id, MediaPlayerState.IDLE, {"volume_level": 0.2})
            for entity_id in entity_ids
        }

    def get(self, entity_id: str) -> State | None:
        return self.values.get(entity_id)


class _Services:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any], str, Context | None]] = []
        self.fail: set[tuple[str, str]] = set()

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
        *,
        blocking: bool,
        context: Context | None,
        target: dict[str, str],
    ) -> None:
        entity_id = target["entity_id"]
        self.calls.append((domain, service, data, entity_id, context))
        if (service, entity_id) in self.fail:
            raise HomeAssistantError(f"simulated failure for {entity_id}")


class _Store:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def async_save(self, value: dict[str, Any]) -> None:
        self.saved.append(value)


def _controller(
    tmp_path: Path, targets: list[str]
) -> tuple[QuranPlayerController, Any]:
    services = _Services()
    loop = asyncio.get_running_loop()
    hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=str(tmp_path)),
        data={},
        loop=loop,
        states=_States(targets),
        services=services,
        async_create_task=lambda coro, name=None: loop.create_task(coro, name=name),
        verify_event_loop_thread=lambda _name: None,
    )
    entry = SimpleNamespace(
        entry_id="test_entry",
        title="Quran Player",
        options={
            CONF_MEDIA_PLAYERS: targets,
            CONF_DEFAULT_RECITER: "yasser_al_dosari",
            CONF_DEFAULT_VOLUME: 35,
        },
    )
    controller = QuranPlayerController(hass, entry)
    controller._store = _Store()
    return controller, hass


def test_declared_home_assistant_runtime_is_importable() -> None:
    """The HA matrix must fail, not skip, when its required runtime cannot import."""
    major, minor, *_rest = (int(part) for part in version("homeassistant").split("."))
    assert (major, minor) >= (2026, 3)


@pytest.mark.asyncio
async def test_single_output_play_volume_and_context(tmp_path: Path) -> None:
    """Volume is set before one direct MP3 playback with context propagation."""
    controller, hass = _controller(tmp_path, ["media_player.office"])
    context = Context()
    await controller.async_play(context)

    assert [call[1] for call in hass.services.calls] == ["volume_set", "play_media"]
    assert all(call[3] == "media_player.office" for call in hass.services.calls)
    assert all(call[4] is context for call in hass.services.calls)
    assert hass.services.calls[-1][2]["media_content_id"].endswith("/001.mp3")
    assert hass.services.calls[-1][2]["media_content_type"] == "audio/mpeg"
    assert controller.active_targets == ("media_player.office",)
    assert controller.state == MediaPlayerState.PLAYING


@pytest.mark.asyncio
async def test_all_output_partial_failure_keeps_successful_session(
    tmp_path: Path,
) -> None:
    """One failed target cannot prevent another from starting."""
    targets = ["media_player.office", "media_player.kitchen"]
    controller, hass = _controller(tmp_path, targets)
    hass.services.fail.add(("play_media", "media_player.kitchen"))

    await controller.async_play()

    assert controller.active_targets == ("media_player.office",)
    assert controller.state == MediaPlayerState.PLAYING
    assert list(controller.last_failures) == ["media_player.kitchen"]


@pytest.mark.asyncio
async def test_all_output_total_failure_never_claims_playing(tmp_path: Path) -> None:
    """A total downstream failure raises clearly and leaves the virtual player idle."""
    targets = ["media_player.office", "media_player.kitchen"]
    controller, hass = _controller(tmp_path, targets)
    hass.services.fail.update(("play_media", target) for target in targets)

    with pytest.raises(HomeAssistantError):
        await controller.async_play()

    assert controller.active_targets == ()
    assert controller.state == MediaPlayerState.IDLE


@pytest.mark.asyncio
async def test_entity_play_media_accepts_home_assistant_keyword(tmp_path: Path) -> None:
    """HA invokes the entity method with the public `media_id` keyword."""
    controller, hass = _controller(tmp_path, ["media_player.office"])
    player = QuranMediaPlayer(controller)

    await player.async_play_media(
        media_type="music",
        media_id="quran-player://yasser_al_dosari/036",
    )

    assert controller.surah_number == 36
    assert hass.services.calls[-1][1] == "play_media"
    assert hass.services.calls[-1][2]["media_content_id"].endswith("/036.mp3")


@pytest.mark.asyncio
async def test_partial_pause_and_stop_keep_failed_target_owned(tmp_path: Path) -> None:
    """A failed speaker remains controllable until a later stop succeeds."""
    targets = ["media_player.office", "media_player.kitchen"]
    controller, hass = _controller(tmp_path, targets)
    await controller.async_play()
    for target in targets:
        hass.states.values[target] = State(target, MediaPlayerState.PLAYING)

    hass.services.fail.add(("media_pause", "media_player.kitchen"))
    await controller.async_pause()
    assert controller.active_targets == tuple(targets)
    assert controller.state == MediaPlayerState.PLAYING

    hass.services.fail.remove(("media_pause", "media_player.kitchen"))
    hass.services.fail.add(("media_stop", "media_player.kitchen"))
    with pytest.raises(HomeAssistantError):
        await controller.async_stop()
    assert controller.active_targets == ("media_player.kitchen",)

    hass.services.fail.clear()
    await controller.async_stop()
    assert controller.active_targets == ()
    assert controller.state == MediaPlayerState.IDLE


@pytest.mark.asyncio
async def test_shutdown_attempts_to_stop_an_owned_session(tmp_path: Path) -> None:
    """Options reload/unload cannot silently abandon active Quran playback."""
    controller, hass = _controller(tmp_path, ["media_player.office"])
    await controller.async_play()
    hass.states.values["media_player.office"] = State(
        "media_player.office", MediaPlayerState.PLAYING
    )

    await controller.async_shutdown()

    assert [call[1] for call in hass.services.calls][-1] == "media_stop"
    assert controller.active_targets == ()
    assert controller.state == MediaPlayerState.IDLE
