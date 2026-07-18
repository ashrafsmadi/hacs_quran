"""Reviewed static reciter and surah catalog for Quran Player.

The integration deliberately ships metadata and links only. It never bundles audio,
downloads ZIP archives, or scrapes a remote catalog at runtime.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from typing import Final

from .const import MEDIA_ID_PREFIX


class CatalogError(ValueError):
    """Raised when a catalog value or media identifier is invalid."""


@dataclass(frozen=True, slots=True)
class Surah:
    """A Quran surah."""

    number: int
    name: str
    arabic_name: str

    @property
    def display_name(self) -> str:
        """Return a stable bilingual display label."""
        return f"{self.number:03d} · {self.name} — {self.arabic_name}"


@dataclass(frozen=True, slots=True)
class Reciter:
    """A reviewed reciter source."""

    key: str
    name: str
    arabic_name: str
    stream_base_url: str
    source_url: str
    available_surahs: tuple[int, ...]
    edition: str = "Hafs 'an Asim"

    @property
    def display_name(self) -> str:
        """Return a bilingual display label."""
        return f"{self.name} — {self.arabic_name}"

    def stream_url(self, surah_number: int) -> str:
        """Return the direct MP3 stream for an available surah."""
        if surah_number not in self.available_surahs:
            raise CatalogError(
                f"Surah {surah_number} is unavailable for {self.display_name}"
            )
        return f"{self.stream_base_url}{surah_number:03d}.mp3"

    def nearest_surah(self, requested: int) -> int:
        """Return the requested surah or the next available one, wrapping once."""
        if not 1 <= requested <= 114:
            raise CatalogError(f"Surah number must be between 1 and 114: {requested}")
        index = bisect_left(self.available_surahs, requested)
        if index == len(self.available_surahs):
            return self.available_surahs[0]
        return self.available_surahs[index]

    def adjacent_surah(self, current: int, step: int) -> int:
        """Return the next or previous available surah, with wraparound."""
        if step not in (-1, 1):
            raise CatalogError(f"Step must be -1 or 1: {step}")
        current = self.nearest_surah(current)
        index = self.available_surahs.index(current)
        return self.available_surahs[(index + step) % len(self.available_surahs)]


_SURAH_ROWS: Final[tuple[tuple[str, str], ...]] = (
    ("Al-Fatihah", "الفاتحة"),
    ("Al-Baqarah", "البقرة"),
    ("Ali 'Imran", "آل عمران"),
    ("An-Nisa", "النساء"),
    ("Al-Ma'idah", "المائدة"),
    ("Al-An'am", "الأنعام"),
    ("Al-A'raf", "الأعراف"),
    ("Al-Anfal", "الأنفال"),
    ("At-Tawbah", "التوبة"),
    ("Yunus", "يونس"),
    ("Hud", "هود"),
    ("Yusuf", "يوسف"),
    ("Ar-Ra'd", "الرعد"),
    ("Ibrahim", "إبراهيم"),
    ("Al-Hijr", "الحجر"),
    ("An-Nahl", "النحل"),
    ("Al-Isra", "الإسراء"),
    ("Al-Kahf", "الكهف"),
    ("Maryam", "مريم"),
    ("Taha", "طه"),
    ("Al-Anbiya", "الأنبياء"),
    ("Al-Hajj", "الحج"),
    ("Al-Mu'minun", "المؤمنون"),
    ("An-Nur", "النور"),
    ("Al-Furqan", "الفرقان"),
    ("Ash-Shu'ara", "الشعراء"),
    ("An-Naml", "النمل"),
    ("Al-Qasas", "القصص"),
    ("Al-'Ankabut", "العنكبوت"),
    ("Ar-Rum", "الروم"),
    ("Luqman", "لقمان"),
    ("As-Sajdah", "السجدة"),
    ("Al-Ahzab", "الأحزاب"),
    ("Saba", "سبأ"),
    ("Fatir", "فاطر"),
    ("Ya-Sin", "يس"),
    ("As-Saffat", "الصافات"),
    ("Sad", "ص"),
    ("Az-Zumar", "الزمر"),
    ("Ghafir", "غافر"),
    ("Fussilat", "فصلت"),
    ("Ash-Shuraa", "الشورى"),
    ("Az-Zukhruf", "الزخرف"),
    ("Ad-Dukhan", "الدخان"),
    ("Al-Jathiyah", "الجاثية"),
    ("Al-Ahqaf", "الأحقاف"),
    ("Muhammad", "محمد"),
    ("Al-Fath", "الفتح"),
    ("Al-Hujurat", "الحجرات"),
    ("Qaf", "ق"),
    ("Adh-Dhariyat", "الذاريات"),
    ("At-Tur", "الطور"),
    ("An-Najm", "النجم"),
    ("Al-Qamar", "القمر"),
    ("Ar-Rahman", "الرحمن"),
    ("Al-Waqi'ah", "الواقعة"),
    ("Al-Hadid", "الحديد"),
    ("Al-Mujadila", "المجادلة"),
    ("Al-Hashr", "الحشر"),
    ("Al-Mumtahanah", "الممتحنة"),
    ("As-Saff", "الصف"),
    ("Al-Jumu'ah", "الجمعة"),
    ("Al-Munafiqun", "المنافقون"),
    ("At-Taghabun", "التغابن"),
    ("At-Talaq", "الطلاق"),
    ("At-Tahrim", "التحريم"),
    ("Al-Mulk", "الملك"),
    ("Al-Qalam", "القلم"),
    ("Al-Haqqah", "الحاقة"),
    ("Al-Ma'arij", "المعارج"),
    ("Nuh", "نوح"),
    ("Al-Jinn", "الجن"),
    ("Al-Muzzammil", "المزمل"),
    ("Al-Muddaththir", "المدثر"),
    ("Al-Qiyamah", "القيامة"),
    ("Al-Insan", "الإنسان"),
    ("Al-Mursalat", "المرسلات"),
    ("An-Naba", "النبأ"),
    ("An-Nazi'at", "النازعات"),
    ("'Abasa", "عبس"),
    ("At-Takwir", "التكوير"),
    ("Al-Infitar", "الانفطار"),
    ("Al-Mutaffifin", "المطففين"),
    ("Al-Inshiqaq", "الانشقاق"),
    ("Al-Buruj", "البروج"),
    ("At-Tariq", "الطارق"),
    ("Al-A'la", "الأعلى"),
    ("Al-Ghashiyah", "الغاشية"),
    ("Al-Fajr", "الفجر"),
    ("Al-Balad", "البلد"),
    ("Ash-Shams", "الشمس"),
    ("Al-Layl", "الليل"),
    ("Ad-Duha", "الضحى"),
    ("Ash-Sharh", "الشرح"),
    ("At-Tin", "التين"),
    ("Al-'Alaq", "العلق"),
    ("Al-Qadr", "القدر"),
    ("Al-Bayyinah", "البينة"),
    ("Az-Zalzalah", "الزلزلة"),
    ("Al-'Adiyat", "العاديات"),
    ("Al-Qari'ah", "القارعة"),
    ("At-Takathur", "التكاثر"),
    ("Al-'Asr", "العصر"),
    ("Al-Humazah", "الهمزة"),
    ("Al-Fil", "الفيل"),
    ("Quraysh", "قريش"),
    ("Al-Ma'un", "الماعون"),
    ("Al-Kawthar", "الكوثر"),
    ("Al-Kafirun", "الكافرون"),
    ("An-Nasr", "النصر"),
    ("Al-Masad", "المسد"),
    ("Al-Ikhlas", "الإخلاص"),
    ("Al-Falaq", "الفلق"),
    ("An-Nas", "الناس"),
)

SURAHS: Final[tuple[Surah, ...]] = tuple(
    Surah(number, name, arabic_name)
    for number, (name, arabic_name) in enumerate(_SURAH_ROWS, start=1)
)
SURAH_BY_NUMBER: Final = {surah.number: surah for surah in SURAHS}

ALL_SURAHS: Final = tuple(range(1, 115))
HAZZA_SURAHS: Final = (
    1,
    12,
    13,
    14,
    15,
    18,
    19,
    25,
    27,
    29,
    30,
    31,
    34,
    36,
    37,
    38,
    39,
    40,
    42,
    44,
    47,
    49,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    67,
    68,
    69,
    70,
    71,
    72,
    73,
    74,
    75,
    76,
    77,
    78,
    79,
    80,
    81,
    82,
    83,
    84,
    85,
    86,
    87,
    88,
    89,
    90,
    91,
    92,
    93,
    94,
    95,
    96,
    97,
    98,
    99,
    100,
    101,
    102,
    103,
    104,
    105,
    106,
    107,
    108,
    109,
    110,
    111,
    112,
    113,
    114,
)

RECITERS: Final[tuple[Reciter, ...]] = (
    Reciter(
        key="hazza_al_balushi",
        name="Hazza Al-Balushi",
        arabic_name="هزاع البلوشي",
        stream_base_url=("https://archive.org/download/Quran-Huzza-Al_Baloushi/"),
        source_url="https://archive.org/details/Quran-Huzza-Al_Baloushi",
        available_surahs=HAZZA_SURAHS,
    ),
    Reciter(
        key="wadee_al_yamani",
        name="Wadee Al-Yamani",
        arabic_name="وديع اليمني",
        stream_base_url="https://archive.org/download/wadie_alyamni/",
        source_url="https://archive.org/details/wadie_alyamni",
        available_surahs=ALL_SURAHS,
    ),
    Reciter(
        key="abdul_basit_abdus_samad_mujawwad",
        name="Abdul Basit Abdus Samad (Mujawwad)",
        arabic_name="عبد الباسط عبد الصمد (مجود)",
        stream_base_url=(
            "https://archive.org/download/"
            "ABDEL-BASIT.ABDEL-SAMAD.MUJAWAD.FULL.HQ.BY-MAHMOUD-ZIED/"
        ),
        source_url=(
            "https://archive.org/details/"
            "ABDEL-BASIT.ABDEL-SAMAD.MUJAWAD.FULL.HQ.BY-MAHMOUD-ZIED"
        ),
        available_surahs=ALL_SURAHS,
        edition="Hafs 'an Asim — Mujawwad",
    ),
    Reciter(
        key="maher_al_muaiqly",
        name="Maher Al-Muaiqly",
        arabic_name="ماهر المعيقلي",
        stream_base_url=("https://archive.org/download/koonoz_blogspot_com_Maher/"),
        source_url="https://archive.org/details/koonoz_blogspot_com_Maher",
        available_surahs=ALL_SURAHS,
    ),
    Reciter(
        key="abdul_rahman_al_sudais",
        name="Abdul Rahman Al-Sudais",
        arabic_name="عبدالرحمن السديس",
        stream_base_url="https://archive.org/download/sudais_2/",
        source_url="https://archive.org/details/sudais_2",
        available_surahs=ALL_SURAHS,
    ),
    Reciter(
        key="mishary_rashid_alafasy",
        name="Mishary Rashid Alafasy",
        arabic_name="مشاري راشد العفاسي",
        stream_base_url=("https://archive.org/download/fm_002_20150413_0654/"),
        source_url="https://archive.org/details/fm_002_20150413_0654",
        available_surahs=ALL_SURAHS,
    ),
    Reciter(
        key="saud_al_shuraim",
        name="Saud Al-Shuraim",
        arabic_name="سعود الشريم",
        stream_base_url="https://server7.mp3quran.net/shur/",
        source_url="https://archive.org/details/TvQuran.com__Al-ShuraimZip",
        available_surahs=ALL_SURAHS,
    ),
    Reciter(
        key="yasser_al_dosari",
        name="Yasser Al-Dosari",
        arabic_name="ياسر الدوسري",
        stream_base_url="https://archive.org/download/dos_6/",
        source_url="https://archive.org/details/dos_6",
        available_surahs=ALL_SURAHS,
    ),
)

RECITER_BY_KEY: Final = {reciter.key: reciter for reciter in RECITERS}
RECITER_KEY_BY_LABEL: Final = {
    reciter.display_name: reciter.key for reciter in RECITERS
}


def get_reciter(key: str) -> Reciter:
    """Return a reciter by stable key."""
    try:
        return RECITER_BY_KEY[key]
    except KeyError as err:
        raise CatalogError(f"Unknown reciter: {key}") from err


def get_surah(number: int) -> Surah:
    """Return a surah by Quran order number."""
    try:
        return SURAH_BY_NUMBER[number]
    except KeyError as err:
        raise CatalogError(f"Unknown surah: {number}") from err


def media_id(reciter_key: str, surah_number: int) -> str:
    """Build an internal media browser identifier."""
    get_reciter(reciter_key).stream_url(surah_number)
    return f"{MEDIA_ID_PREFIX}{reciter_key}/{surah_number:03d}"


def parse_media_id(value: str) -> tuple[str, int]:
    """Parse and validate an internal media browser identifier."""
    if not value.startswith(MEDIA_ID_PREFIX):
        raise CatalogError("This media item does not belong to Quran Player")
    parts = value.removeprefix(MEDIA_ID_PREFIX).strip("/").split("/")
    if len(parts) != 2:
        raise CatalogError(f"Invalid Quran Player media identifier: {value}")
    reciter_key, raw_surah = parts
    try:
        surah_number = int(raw_surah)
    except ValueError as err:
        raise CatalogError(
            f"Invalid surah number in media identifier: {value}"
        ) from err
    get_reciter(reciter_key).stream_url(surah_number)
    return reciter_key, surah_number
