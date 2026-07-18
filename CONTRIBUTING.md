# Contributing

Thank you for improving Quran Player.

## Before opening a change

- Keep the integration limited to one Home Assistant device and one config entry.
- Do not add audio, ZIP archives, scraped catalogs, credentials, telemetry, or
  network access during setup.
- Do not add a reciter or replace a recording source without documented provenance,
  availability validation, and rights review.
- Preserve partial-failure isolation and active-session target safety.
- Update `README.md` and `CHANGELOG.md` for every public behavior change.
- Never include Home Assistant tokens, passwords, private URLs, or logs containing
  private household data.

## Local checks

Quran Player targets the Python version required by its supported Home Assistant
release.

```bash
python3.14 -m venv .venv
.venv/bin/pip install "homeassistant==2026.7.2" pytest pytest-asyncio pillow ruff
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

Also verify a clean HACS installation and real playback on at least one supported
media player before proposing a release.

## Pull requests

Describe the user impact, design, source/provenance changes, tests run, and any
remaining limitation. Keep commits focused and do not mix unrelated formatting or
workspace files into the change.
