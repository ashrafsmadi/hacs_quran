# Changelog

All notable public changes to Quran Player are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-07-18

### Added

- Initial HACS custom integration with UI-only configuration and one config entry.
- One service-backed Quran Player device containing one aggregate media player,
  reciter/surah/output selectors, and a playback-duration control.
- One-output and all-output playback through existing Home Assistant media players.
- Per-target remembered volume, all-output volume, mute, seek, and partial-failure
  isolation.
- Session-ownership safeguards that retain failed outputs for stop retries and stop
  owned playback before integration reload, unload, or removal.
- Play, resume, pause, stop, next/previous available surah, repeat Off/One/All, and
  generation-guarded natural track advancement.
- 0–720 minute wall-clock sleep timer; `0` disables the limit.
- Static reviewed catalog of exactly eight reciters and 114 bilingual surah names.
- Verified 78-surah availability map for Hazza Al-Balushi; navigation skips gaps.
- Direct Internet Archive streams for seven supplied collections and the documented
  MP3Quran per-surah stream for Saud Al-Shuraim.
- Reciter → Surah media browsing, persistent selections, English/Arabic UI, local
  brand assets, HACS metadata, tests, and automated validation.
- Serialized cross-entity commands, translated playback errors, and delayed
  end-of-track confirmation across common media-player terminal states.
- Detailed installation, migration, troubleshooting, privacy, source provenance,
  and recording-rights documentation.

[1.0.0]: https://github.com/ashrafsmadi/hacs_quran/releases/tag/v1.0.0
