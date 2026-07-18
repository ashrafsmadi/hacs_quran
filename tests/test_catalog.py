"""Tests for the reviewed static reciter/surah catalog."""

from __future__ import annotations

from types import ModuleType
from urllib.parse import urlparse

import pytest


def test_exact_approved_catalog(catalog: ModuleType) -> None:
    """The public integration must expose exactly the owner's eight reciters."""
    expected = (
        (
            "hazza_al_balushi",
            "Hazza Al-Balushi",
            "هزاع البلوشي",
            "https://archive.org/download/Quran-Huzza-Al_Baloushi/",
            "https://archive.org/details/Quran-Huzza-Al_Baloushi",
            78,
        ),
        (
            "wadee_al_yamani",
            "Wadee Al-Yamani",
            "وديع اليمني",
            "https://archive.org/download/wadie_alyamni/",
            "https://archive.org/details/wadie_alyamni",
            114,
        ),
        (
            "abdul_basit_abdus_samad_mujawwad",
            "Abdul Basit Abdus Samad (Mujawwad)",
            "عبد الباسط عبد الصمد (مجود)",
            (
                "https://archive.org/download/"
                "ABDEL-BASIT.ABDEL-SAMAD.MUJAWAD.FULL.HQ.BY-MAHMOUD-ZIED/"
            ),
            (
                "https://archive.org/details/"
                "ABDEL-BASIT.ABDEL-SAMAD.MUJAWAD.FULL.HQ.BY-MAHMOUD-ZIED"
            ),
            114,
        ),
        (
            "maher_al_muaiqly",
            "Maher Al-Muaiqly",
            "ماهر المعيقلي",
            "https://archive.org/download/koonoz_blogspot_com_Maher/",
            "https://archive.org/details/koonoz_blogspot_com_Maher",
            114,
        ),
        (
            "abdul_rahman_al_sudais",
            "Abdul Rahman Al-Sudais",
            "عبدالرحمن السديس",
            "https://archive.org/download/sudais_2/",
            "https://archive.org/details/sudais_2",
            114,
        ),
        (
            "mishary_rashid_alafasy",
            "Mishary Rashid Alafasy",
            "مشاري راشد العفاسي",
            "https://archive.org/download/fm_002_20150413_0654/",
            "https://archive.org/details/fm_002_20150413_0654",
            114,
        ),
        (
            "saud_al_shuraim",
            "Saud Al-Shuraim",
            "سعود الشريم",
            "https://server7.mp3quran.net/shur/",
            "https://archive.org/details/TvQuran.com__Al-ShuraimZip",
            114,
        ),
        (
            "yasser_al_dosari",
            "Yasser Al-Dosari",
            "ياسر الدوسري",
            "https://archive.org/download/dos_6/",
            "https://archive.org/details/dos_6",
            114,
        ),
    )
    actual = tuple(
        (
            reciter.key,
            reciter.name,
            reciter.arabic_name,
            reciter.stream_base_url,
            reciter.source_url,
            len(reciter.available_surahs),
        )
        for reciter in catalog.RECITERS
    )
    assert actual == expected
    assert len(catalog.RECITER_BY_KEY) == 8
    assert sum(len(item.available_surahs) for item in catalog.RECITERS) == 876


def test_complete_surah_metadata(catalog: ModuleType) -> None:
    """All Quran order numbers have unique, non-empty bilingual names."""
    assert [surah.number for surah in catalog.SURAHS] == list(range(1, 115))
    assert len({surah.name for surah in catalog.SURAHS}) == 114
    assert all(surah.name and surah.arabic_name for surah in catalog.SURAHS)


def test_source_urls_are_direct_https_audio(catalog: ModuleType) -> None:
    """No generated Cast URL may be a ZIP, dynamic archive, or query download."""
    for reciter in catalog.RECITERS:
        assert tuple(sorted(set(reciter.available_surahs))) == reciter.available_surahs
        assert all(1 <= number <= 114 for number in reciter.available_surahs)
        for number in reciter.available_surahs:
            url = reciter.stream_url(number)
            parsed = urlparse(url)
            assert parsed.scheme == "https"
            assert parsed.query == ""
            assert parsed.path.endswith(f"/{number:03d}.mp3")
            assert ".zip" not in url.lower()
            assert "/compress/" not in url.lower()


def test_hazza_has_only_verified_surahs_and_skips_gaps(catalog: ModuleType) -> None:
    """Hazza selection and navigation never synthesize known-missing filenames."""
    hazza = catalog.get_reciter("hazza_al_balushi")
    assert len(hazza.available_surahs) == 78
    assert 1 in hazza.available_surahs
    assert 2 not in hazza.available_surahs
    assert hazza.adjacent_surah(1, 1) == 12
    assert hazza.adjacent_surah(12, -1) == 1
    assert hazza.adjacent_surah(114, 1) == 1
    assert hazza.nearest_surah(2) == 12
    with pytest.raises(catalog.CatalogError):
        hazza.stream_url(2)


def test_media_identifier_round_trip_and_validation(catalog: ModuleType) -> None:
    """Only reviewed catalog items can be sent from the media browser to playback."""
    value = catalog.media_id("yasser_al_dosari", 36)
    assert value == "quran-player://yasser_al_dosari/036"
    assert catalog.parse_media_id(value) == ("yasser_al_dosari", 36)

    for invalid in (
        "https://example.com/audio.mp3",
        "quran-player://unknown/001",
        "quran-player://hazza_al_balushi/002",
        "quran-player://yasser_al_dosari/not-a-number",
        "quran-player://yasser_al_dosari/001/extra",
    ):
        with pytest.raises(catalog.CatalogError):
            catalog.parse_media_id(invalid)
