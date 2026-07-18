# Quran Player for Home Assistant

[![Validate](https://github.com/ashrafsmadi/hacs_quran/actions/workflows/validate.yml/badge.svg)](https://github.com/ashrafsmadi/hacs_quran/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/ashrafsmadi/hacs_quran)](https://github.com/ashrafsmadi/hacs_quran/releases)
[![License: MIT](https://img.shields.io/badge/code%20license-MIT-green.svg)](LICENSE)

Quran Player is a HACS custom integration that turns existing Home Assistant media
players into one focused Quran playback device. Choose a reciter and surah, play on
one output or every configured output, control volume per output or as a group, seek
within a recitation, and set a wall-clock playback limit.

The integration contains no audio. It streams only the selected reciter and surah
from the reviewed sources listed below.

## Highlights

- One Home Assistant **device**, regardless of how many output players you add.
- Works through existing `media_player` entities—no direct Cast protocol or new
  speaker devices.
- Supports Chromecast speakers, Cast speaker groups, and other Home Assistant media
  players that accept a public HTTPS MP3 URL.
- Eight curated reciters with bilingual Arabic/English names.
- All 114 bilingual surah names, filtered to files actually available for the
  selected reciter.
- Play, resume, pause, stop, next, previous, seek, mute, and repeat controls.
- Choose one output or **All configured players**.
- Set volume for the selected output or all outputs; individual values are
  remembered.
- Optional 0–720 minute playback duration. `0` means no time limit.
- Reciter → Surah browsing from the Quran Player media browser.
- English and Arabic Home Assistant UI translations.
- Partial output failures are isolated: one offline speaker does not block the
  others.
- No YAML helper, watchdog automation, website scraper, ZIP extraction, or bundled
  recordings.

## What Home Assistant creates

Quran Player allows one config entry and registers one service-backed device. The
device contains these entities:

| Entity type | Purpose |
|---|---|
| Media player | Main playback, volume, seek, repeat, source/output, and media browser |
| Reciter select | Chooses one of the eight reviewed reciters |
| Surah select | Shows only surahs available for the selected reciter |
| Playback output select | Chooses one configured player or all configured players |
| Playback duration number | Stops the session after 0–720 wall-clock minutes |

Entity IDs are assigned by Home Assistant and can be renamed safely.

## Requirements

- Home Assistant **2026.3.0 or newer**
- HACS, for the recommended installation method
- At least one existing `media_player` entity that supports `play_media` with a
  remote HTTPS MP3 URL
- Internet access from each playback device to Internet Archive or MP3Quran

The minimum HA version is 2026.3 because that release added local brand-image
support for custom integrations.

## Installation with HACS

Use this button to open the repository in HACS:

[![Open your Home Assistant instance and add this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ashrafsmadi&repository=hacs_quran&category=integration)

Or add it manually:

1. Open **HACS → Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Enter `https://github.com/ashrafsmadi/hacs_quran`.
4. Select category **Integration**, then add and download **Quran Player**.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration**.
7. Search for **Quran Player**.
8. Select one or more playback outputs, a default reciter, and a default volume.

To change the output list later, open the Quran Player integration and choose
**Configure**. Saving options safely stops an active Quran Player session, then
reloads the integration once.

### Manual installation

Copy `custom_components/quran_player` into your Home Assistant configuration's
`custom_components` directory, restart Home Assistant, and add Quran Player from
**Settings → Devices & services**. HACS is recommended because it handles updates.

## Using the player

### Select a reciter and surah

Use the **Reciter** and **Surah** selects on the Quran Player device. Changing either
selection while playing starts the newly selected recitation once. The media-player
browse button provides the same catalog as `Reciter → Surah`.

### Choose one speaker or all speakers

Use either the **Playback output** select or the main media player's source selector.
Both control the same setting:

- Select a named entity to control only that output.
- Select **All configured players** to fan commands out to every configured output.

Quran Player sends actions concurrently, but independent speakers are not guaranteed
to be sample-synchronized. If synchronization matters, create a native Chromecast or
speaker group in its own integration and select that group as one output.

### Volume per device and for all devices

The main media-player volume applies to the current playback-output selection:

1. Select one output and set its desired volume. Quran Player remembers that value.
2. Repeat for other outputs if they need different levels.
3. Select **All configured players** to set the same value on every output.

The configured default volume is used for a target until Quran Player remembers a
specific value. A player that does not support Home Assistant volume actions may
still support playback; its volume failure is reported without blocking other
players.

### Playback time and seeking

There are two different time controls:

- **Seek** changes the current position in seconds. It works only when the selected
  real media-player integration supports seeking remote MP3 streams.
- **Playback duration** is a wall-clock sleep timer in minutes. `0` disables the
  timer. A positive value stops the whole Quran Player session after that many
  minutes. Changing it while playing replaces the current timer. The timer continues
  while paused and is not reset when moving to another surah.

Playback and timers intentionally do not resume automatically after a Home Assistant
restart. Unloading, reloading, or removing the integration first sends Stop to every
output still owned by the Quran Player session.

### Repeat behavior

The main media player's standard repeat control determines natural end-of-track
behavior:

| Repeat | Behavior when the current surah finishes |
|---|---|
| Off | Stop the Quran Player session |
| One | Replay the current surah |
| All | Play the next available surah and wrap after the last one |

Repeat defaults to **All**, providing continuous playback without the old watchdog
automation. Use Quran Player's own Stop control for an intentional stop. Stopping a
real output directly may look like a natural end to Home Assistant.

## Included reciters and audio sources

Only these eight reciters are included. The URLs are static metadata in the
integration; no remote catalog is fetched during setup.

| Reciter | Availability | Playback source/provenance |
|---|---:|---|
| Hazza Al-Balushi — هزاع البلوشي | 78 surahs | [Internet Archive](https://archive.org/details/Quran-Huzza-Al_Baloushi) |
| Wadee Al-Yamani — وديع اليمني | 114 | [Internet Archive](https://archive.org/details/wadie_alyamni) |
| Abdul Basit Abdus Samad (Mujawwad) — عبد الباسط عبد الصمد | 114 | [Internet Archive](https://archive.org/details/ABDEL-BASIT.ABDEL-SAMAD.MUJAWAD.FULL.HQ.BY-MAHMOUD-ZIED) |
| Maher Al-Muaiqly — ماهر المعيقلي | 114 | [Internet Archive](https://archive.org/details/koonoz_blogspot_com_Maher) |
| Abdul Rahman Al-Sudais — عبدالرحمن السديس | 114 | [Internet Archive](https://archive.org/details/sudais_2) |
| Mishary Rashid Alafasy — مشاري راشد العفاسي | 114 | [Internet Archive](https://archive.org/details/fm_002_20150413_0654) |
| Saud Al-Shuraim — سعود الشريم | 114 | Supplied [Internet Archive ZIP](https://archive.org/details/TvQuran.com__Al-ShuraimZip); direct playback from [MP3Quran](https://www.mp3quran.net/eng/api) |
| Yasser Al-Dosari — ياسر الدوسري | 114 | [Internet Archive](https://archive.org/details/dos_6) |

The supplied Hazza Al-Balushi collection does not contain every surah. Quran Player
exposes only these verified numbers and skips gaps with Next/Previous:

`1, 12–15, 18–19, 25, 27, 29–31, 34, 36–40, 42, 44, 47, 49–57, 67–114`

The supplied Al-Shuraim archive contains all files inside a large ZIP, which Cast
devices cannot seek reliably. Quran Player therefore uses MP3Quran's documented,
range-capable per-surah stream for this reciter.

### Recording rights and attribution

This repository does **not** redistribute, cache, modify, or sublicense recordings.
It sends third-party HTTPS links to media players on demand. The MIT license in this
repository covers the integration code and original brand asset only; it does not
cover Quran recordings, reciter performances, or third-party metadata. Rights remain
with the respective reciters, publishers, and hosts.

Internet Archive records for these supplied items do not declare a uniform open
content license. In particular, the Maher source describes noncommercial-use
conditions. Review the source page and laws applicable to your use. Quran Player is
unaffiliated with the reciters, Internet Archive, MP3Quran, SurahQuran, Home Assistant,
or HACS.

## Migrating from the old automation

Do not run the old watchdog automation and Quran Player at the same time; they may
fight over the same speaker.

1. Install and configure Quran Player first.
2. Select the same speaker used by the old automation and verify play, stop, next,
   volume, and Home Assistant restart behavior.
3. Disable the old `Quran: Keep Office speaker playing` automation (its entity ID may
   be `automation.quran_keep_office_speaker_playing`).
4. After confirming the new integration is stable, remove the old
   `input_number.office_quran_track` helper and its YAML definition if they are no
   longer used anywhere else.
5. Keep a Home Assistant configuration backup before editing YAML.

The integration never edits `automations.yaml` or `configuration.yaml` itself.

## Troubleshooting

### The player says every target failed

- Confirm the real entity is available in **Developer tools → States**.
- Test that entity with the standard `media_player.play_media` action and a public
  MP3 URL.
- Check that the speaker can reach the internet and resolve public DNS.
- Review Home Assistant logs for `quran_player` and the target integration.

### One speaker works and another does not

This is expected partial-failure isolation. Verify that the failing integration
supports remote URL playback. Some TV and receiver entities expose `media_player`
controls but accept only local inputs or vendor-specific media IDs.

### Seek does not work

The reviewed sources support HTTP byte ranges, but the target media-player
integration must also implement Home Assistant's seek action. Playback and the
sleep timer still work when seek is unsupported.

### Speakers start at slightly different times

Quran Player dispatches commands concurrently but does not create a synchronized
audio clock. Use a native speaker group and select it as one output.

### A source becomes unavailable

Recordings are hosted by third parties and availability can change. Open a GitHub
issue with the reciter, surah number, target entity integration, and relevant log
message. Do not include Home Assistant tokens, passwords, or private URLs.

## Updating and removal

- Update through **HACS → Integrations → Quran Player**, then restart Home Assistant
  if HACS requests it.
- To remove the integration, delete its config entry under **Settings → Devices &
  services**, remove it from HACS, and restart. Deleting the config entry removes
  Quran Player's stored selections; it stops its active session but never deletes or
  reconfigures target players.

## Privacy and network behavior

- No account, API key, telemetry, analytics, or cloud registration is used.
- Entity IDs and per-target preferences stay in Home Assistant's local storage.
- On playback, the chosen speaker contacts the selected third-party audio host. That
  host can receive the speaker's public IP address and normal HTTP request metadata.
- Setup and normal selection changes do not enumerate remote catalogs or download
  archives.

## Development

The source is under `custom_components/quran_player`. Validation includes Ruff,
pytest, Home Assistant import/controller tests, hassfest, and the HACS action.

```bash
python3.14 -m venv .venv
.venv/bin/pip install "homeassistant==2026.7.2" pytest pytest-asyncio pillow ruff
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change. Public behavior
changes must also be added to [CHANGELOG.md](CHANGELOG.md).

## License

Integration code and the original repository brand asset are released under the
[MIT License](LICENSE). Third-party Quran recordings are not included in that
license.
