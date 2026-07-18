"""Constants for the Quran Player integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "quran_player"
NAME: Final = "Quran Player"
VERSION: Final = "1.0.0"

PLATFORMS: Final = (Platform.MEDIA_PLAYER, Platform.SELECT, Platform.NUMBER)

CONF_MEDIA_PLAYERS: Final = "media_players"
CONF_DEFAULT_RECITER: Final = "default_reciter"
CONF_DEFAULT_VOLUME: Final = "default_volume"

DEFAULT_RECITER: Final = "yasser_al_dosari"
DEFAULT_VOLUME: Final = 0.35
DEFAULT_SURAH: Final = 1
DEFAULT_PLAYBACK_DURATION: Final = 0

ALL_TARGETS: Final = "__all__"
ALL_TARGETS_LABEL: Final = "All configured players"

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = f"{DOMAIN}.state"

SIGNAL_STATE_UPDATED: Final = f"{DOMAIN}_state_updated"

ATTRIBUTION: Final = (
    "Audio is streamed from Internet Archive and MP3Quran; rights remain with "
    "the respective reciters and publishers."
)

MEDIA_MIME_TYPE: Final = "audio/mpeg"
MEDIA_ID_PREFIX: Final = "quran-player://"
