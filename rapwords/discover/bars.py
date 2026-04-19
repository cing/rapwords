"""Extract rhyming bars/couplets around a target word in lyrics."""

from __future__ import annotations

import itertools
import operator
import re

import pronouncing


def _get_rhyming_part(word: str) -> str | None:
    """Get the rhyming part of a word's phonetic representation."""
    clean = re.sub(r"[^a-zA-Z]", "", word)
    if not clean:
        return None
    phones = pronouncing.phones_for_word(clean.lower())
    if not phones:
        return None
    return pronouncing.rhyming_part(phones[0])[:2]


def _tag_lines_with_rhymes(lines: list[str]) -> list[tuple[str, str]]:
    """Tag each line with its end-word rhyming part. Returns (rhyme_tag, line) pairs."""
    tagged = []
    for line in lines:
        words = line.split()
        if not words:
            continue
        # Use last word, strip punctuation
        last_word = re.sub(r"[^a-zA-Z]", "", words[-1])
        rhyme = _get_rhyming_part(last_word)
        tag = rhyme if rhyme else f"_no_rhyme_{len(tagged)}"
        tagged.append((tag, line))
    return tagged


def extract_bars(lyrics: str, target_word: str, context_lines: int = 4) -> list[str]:
    """Extract the rhyming bar group containing the target word.

    Strategy:
    1. Group consecutive lines by rhyming end-words
    2. Find the group containing the target word
    3. Fallback: return ±context_lines around the first occurrence
    """
    lines = [l.strip() for l in lyrics.split("\n") if l.strip()]
    target_lower = target_word.lower()

    # Find lines containing the target word
    target_line_indices = [
        i for i, line in enumerate(lines)
        if target_lower in line.lower().split() or target_lower in re.sub(r"[^a-z\s]", "", line.lower()).split()
    ]

    if not target_line_indices:
        return []

    # Try rhyme-based grouping
    tagged = _tag_lines_with_rhymes(lines)
    if tagged:
        # Group consecutive lines with same rhyme tag
        grouped = []
        for _key, group in itertools.groupby(tagged, operator.itemgetter(0)):
            grouped.append([line for _, line in group])

        # Find the group containing the target word
        for group in grouped:
            for line in group:
                if target_lower in line.lower().split() or target_lower in re.sub(r"[^a-z\s]", "", line.lower()).split():
                    # If the group is reasonable size (2-8 lines), use it
                    if 2 <= len(group) <= 8:
                        return group

    # Fallback: context window around first occurrence
    idx = target_line_indices[0]
    start = max(0, idx - context_lines // 2)
    end = min(len(lines), idx + context_lines // 2 + 1)
    # Ensure we get at least context_lines
    if end - start < context_lines:
        if start == 0:
            end = min(len(lines), context_lines)
        else:
            start = max(0, end - context_lines)
    return lines[start:end]


def _split_lyric_lines(full_lyrics: str) -> list[str]:
    """Split lyrics into stripped non-empty lines (same convention as extract_bars)."""
    return [l.strip() for l in full_lyrics.split("\n") if l.strip()]


def _locate_window(all_lines: list[str], current_bars: list[str]) -> tuple[int, int] | None:
    """Find [start, end) in all_lines that matches current_bars. None if not found."""
    if not current_bars:
        return None
    first = current_bars[0]
    last = current_bars[-1]
    n = len(current_bars)

    # Exact-sequence match first
    for i in range(len(all_lines) - n + 1):
        if all_lines[i : i + n] == current_bars:
            return (i, i + n)

    # Looser: first-line match, then verify last-line position
    for i, line in enumerate(all_lines):
        if line == first:
            for j in range(i, len(all_lines)):
                if all_lines[j] == last and j >= i:
                    return (i, j + 1)

    # Last resort: substring match on first line
    for i, line in enumerate(all_lines):
        if first in line:
            # Pick a window the same length as current_bars, clipped to bounds
            end = min(len(all_lines), i + n)
            return (i, end)

    return None


def nudge_bars(
    full_lyrics: str,
    current_bars: list[str],
    delta_before: int = 0,
    delta_after: int = 0,
) -> list[str]:
    """Return an adjusted bar window, growing/shrinking relative to current_bars.

    - delta_before > 0  prepends that many lines from the song.
    - delta_before < 0  drops that many lines from the top of the current window.
    - delta_after  > 0  appends that many lines from the song.
    - delta_after  < 0  drops that many lines from the bottom of the current window.

    Clipped to song bounds and to always keep at least one line. If the current
    bars can't be located inside full_lyrics, returns current_bars unchanged.
    """
    all_lines = _split_lyric_lines(full_lyrics)
    located = _locate_window(all_lines, current_bars)
    if located is None:
        return current_bars

    start, end = located
    new_start = max(0, start - delta_before)
    new_end = min(len(all_lines), end + delta_after)
    # Guarantee a non-empty window
    if new_end <= new_start:
        new_end = min(len(all_lines), new_start + 1)
    return all_lines[new_start:new_end]
