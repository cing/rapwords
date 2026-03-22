"""Identify 'big words' in lyrics using word frequency and dictionary data."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from rapwords.config import ROOT_DIR

ASSETS_DIR = ROOT_DIR / "archive" / "assets"
FREQ_FILE = ASSETS_DIR / "count_1w.txt"
DICT_FILE = ASSETS_DIR / "TWL06.txt"

# Thresholds from the original PyCon 2016 notebook
MAX_FREQUENCY = 400_000
MIN_WORD_LENGTH = 5


@lru_cache(maxsize=None)
def load_big_words(
    max_frequency: int = MAX_FREQUENCY,
    min_length: int = MIN_WORD_LENGTH,
) -> set[str]:
    """Load the set of 'big words' — rare English words from the Scrabble dictionary.

    A word qualifies if it:
    1. Appears in the Scrabble Tournament Word List (TWL06)
    2. Has a frequency count < max_frequency in the Norvig word frequency list
    3. Is at least min_length characters long

    Lower max_frequency = stricter (rarer words only).
    Higher min_length = longer words only.
    """
    # Load Scrabble dictionary
    dict_words = set()
    for line in DICT_FILE.read_text().splitlines():
        w = line.strip().lower()
        if w:
            dict_words.add(w)

    # Load word frequencies and filter
    big_words = set()
    for line in FREQ_FILE.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        word, count_str = parts[0].lower(), parts[1]
        try:
            count = int(count_str)
        except ValueError:
            continue
        if count < max_frequency and len(word) >= min_length and word in dict_words:
            big_words.add(word)

    return big_words


def find_big_words(
    lyrics: str,
    max_frequency: int = MAX_FREQUENCY,
    min_length: int = MIN_WORD_LENGTH,
) -> list[str]:
    """Find all 'big words' in a lyrics string. Returns deduplicated list."""
    big_words = load_big_words(max_frequency=max_frequency, min_length=min_length)
    # Normalize: lowercase, split on whitespace, strip punctuation
    found = []
    seen = set()
    for token in lyrics.lower().split():
        clean = re.sub(r"[^a-zA-Z]", "", token)
        if clean in big_words and clean not in seen:
            found.append(clean)
            seen.add(clean)
    return found
