"""Fixtures that keep pure catalog tests independent of Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def catalog() -> ModuleType:
    """Load catalog.py in an isolated package with its one constant dependency."""
    package_name = "_quran_catalog_test"
    package = ModuleType(package_name)
    package.__path__ = [str(ROOT / "custom_components/quran_player")]
    sys.modules[package_name] = package

    const = ModuleType(f"{package_name}.const")
    const.MEDIA_ID_PREFIX = "quran-player://"
    sys.modules[const.__name__] = const

    module_name = f"{package_name}.catalog"
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / "custom_components/quran_player/catalog.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
