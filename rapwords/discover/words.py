"""Identify 'big words' in lyrics using Zipf frequency and dictionary data."""

from __future__ import annotations

import re
from functools import lru_cache

from wordfreq import zipf_frequency

from rapwords.config import ROOT_DIR

ASSETS_DIR = ROOT_DIR / "archive" / "assets"
DICT_FILE = ASSETS_DIR / "TWL06.txt"

# Zipf scale: 7-8 = ultra-common ("the"), 5-6 = common ("people"),
# 3-4 = uncommon ("ubiquitous"), 1-2 = rare ("defenestrate")
MAX_ZIPF = 3.5
MIN_WORD_LENGTH = 5
# Words below this Zipf are too rare to plausibly be slang — skip the stricter
# dictionary check for them. Guards legit but unusual vocabulary like
# "defenestrate" which NLTK's wordlist happens to miss.
SLANG_ZIPF_FLOOR = 2.5


@lru_cache(maxsize=None)
def _load_scrabble_dict() -> frozenset[str]:
    """Load the Scrabble Tournament Word List (TWL06)."""
    words = set()
    for line in DICT_FILE.read_text().splitlines():
        w = line.strip().lower()
        if w:
            words.add(w)
    return frozenset(words)


@lru_cache(maxsize=None)
def _load_standard_dict() -> frozenset[str]:
    """Load NLTK's curated English wordlist. Downloads on first use.

    TWL06 (Scrabble) is permissive and admits many short slang terms ("homie",
    "shorty", "finna"). NLTK's `words` corpus is a stricter standard-English
    dictionary; intersecting the two keeps the dense-vocabulary long tail
    (ameliorate, defenestrate, juxtapose) while filtering typical rap slang.
    """
    import nltk

    try:
        from nltk.corpus import words
        word_list = words.words()
    except LookupError:
        nltk.download("words", quiet=True)
        from nltk.corpus import words
        word_list = words.words()

    return frozenset(w.lower() for w in word_list)


def is_likely_slang(word: str) -> bool:
    """True if the word is in the permissive Scrabble list but not in the
    stricter NLTK standard-English wordlist."""
    return word.lower() not in _load_standard_dict()


def find_big_words(
    lyrics: str,
    max_zipf: float = MAX_ZIPF,
    min_length: int = MIN_WORD_LENGTH,
    slang_filter: bool = True,
) -> list[str]:
    """Find all 'big words' in a lyrics string. Returns deduplicated list.

    A word qualifies if it:
    1. Appears in the Scrabble Tournament Word List (TWL06)
    2. Has a Zipf frequency score < max_zipf (lower = rarer)
    3. Is at least min_length characters long
    4. (if slang_filter) Appears in NLTK's standard English wordlist

    Zipf scale reference:
        7-8  ultra-common ("the", "of")
        5-6  common ("people", "important")
        3-4  uncommon ("ubiquitous", "impediment")
        1-2  rare ("defenestrate", "juxtapose")
    """
    dict_words = _load_scrabble_dict()
    standard_words = _load_standard_dict() if slang_filter else None

    found = []
    seen = set()
    for token in lyrics.lower().split():
        clean = re.sub(r"[^a-zA-Z]", "", token)
        if not clean or len(clean) < min_length or clean in seen:
            continue
        if clean not in dict_words:
            continue
        z = zipf_frequency(clean, "en")
        if z >= max_zipf:
            continue
        if (
            standard_words is not None
            and z >= SLANG_ZIPF_FLOOR
            and clean not in standard_words
        ):
            seen.add(clean)
            continue
        found.append(clean)
        seen.add(clean)
    return found
