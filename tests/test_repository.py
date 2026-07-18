"""Distribution, localization, branding, and public-repository hygiene tests."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components/quran_player"


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _leaf_paths(value: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {prefix}
    result: set[tuple[str, ...]] = set()
    for key, child in value.items():
        result |= _leaf_paths(child, (*prefix, key))
    return result


def test_hacs_and_manifest_metadata_match() -> None:
    """HACS and HA metadata describe one versioned singleton integration."""
    hacs = _json(ROOT / "hacs.json")
    manifest = _json(COMPONENT / "manifest.json")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert hacs == {"name": "Quran Player", "homeassistant": "2026.3.0"}
    assert manifest["domain"] == "quran_player"
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["iot_class"] == "local_push"
    assert manifest["requirements"] == []
    assert manifest["version"] == "1.0.0"
    assert 'version = "1.0.0"' in project
    assert (
        len([path for path in (ROOT / "custom_components").iterdir() if path.is_dir()])
        == 1
    )


def test_current_custom_translation_layout_is_complete() -> None:
    """English and Arabic ship the same complete runtime key structure."""
    assert not (COMPONENT / "strings.json").exists()
    english = _json(COMPONENT / "translations/en.json")
    arabic = _json(COMPONENT / "translations/ar.json")
    assert _leaf_paths(english) == _leaf_paths(arabic)
    assert not any(
        isinstance(value, str) and "[%key:" in value
        for tree in (english, arabic)
        for value in _walk_values(tree)
    )


def _walk_values(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        return [leaf for child in value.values() for leaf in _walk_values(child)]
    return [value]


def test_local_brand_assets_are_valid_square_pngs() -> None:
    """HA 2026.3+ can load both normal and high-density local icons."""
    expected = {"icon.png": (256, 256), "icon@2x.png": (512, 512)}
    for filename, size in expected.items():
        path = COMPONENT / "brand" / filename
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == size
            assert image.mode in {"RGB", "RGBA"}


def test_no_audio_archives_or_private_working_docs_are_publishable() -> None:
    """The public tree contains code/metadata only and ignores private logs."""
    forbidden_suffixes = {".mp3", ".m4a", ".ogg", ".wav", ".zip", ".tar", ".gz"}
    assert not [
        path for path in ROOT.rglob("*") if path.suffix.lower() in forbidden_suffixes
    ]

    ignored = subprocess.run(
        ["git", "check-ignore", "agent.md", "docs/PROJECT_LOG.md"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert ignored == ["agent.md", "docs/PROJECT_LOG.md"]
