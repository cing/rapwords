"""Identify 'big words' in lyrics using Zipf frequency and dictionary data."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from wordfreq import zipf_frequency

from rapwords.config import ROOT_DIR

ASSETS_DIR = ROOT_DIR / "archive" / "assets"
DICT_FILE = ASSETS_DIR / "TWL06.txt"

# Zipf scale: 7-8 = ultra-common ("the"), 5-6 = common ("people"),
# 3-4 = uncommon ("ubiquitous"), 1-2 = rare ("defenestrate")
MAX_ZIPF = 3.5
MIN_WORD_LENGTH = 5


@lru_cache(maxsize=None)
def _load_scrabble_dict() -> frozenset[str]:
    """Load the Scrabble Tournament Word List (TWL06)."""
    words = set()
    for line in DICT_FILE.read_text().splitlines():
        w = line.strip().lower()
        if w:
            words.add(w)
    return frozenset(words)


def find_big_words(
    lyrics: str,
    max_zipf: float = MAX_ZIPF,
    min_length: int = MIN_WORD_LENGTH,
) -> list[str]:
    """Find all 'big words' in a lyrics string. Returns deduplicated list.

    A word qualifies if it:
    1. Appears in the Scrabble Tournament Word List (TWL06)
    2. Has a Zipf frequency score < max_zipf (lower = rarer)
    3. Is at least min_length characters long

    Zipf scale reference:
        7-8  ultra-common ("the", "of")
        5-6  common ("people", "important")
        3-4  uncommon ("ubiquitous", "impediment")
        1-2  rare ("defenestrate", "juxtapose")
    """
    dict_words = _load_scrabble_dict()
    found = []
    seen = set()
    for token in lyrics.lower().split():
        clean = re.sub(r"[^a-zA-Z]", "", token)
        if not clean or len(clean) < min_length or clean in seen:
            continue
        if clean in dict_words and zipf_frequency(clean, "en") < max_zipf:
            found.append(clean)
            seen.add(clean)
    return found
