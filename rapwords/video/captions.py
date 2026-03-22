"""Download and search YouTube auto-captions to find lyric timestamps."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rapwords.models import RapWordsPost


@dataclass
class CaptionEntry:
    start: float  # seconds
    end: float
    text: str


def download_captions(video_id: str) -> list[CaptionEntry] | None:
    """Download auto-captions for a YouTube video. Returns parsed entries or None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = str(Path(tmpdir) / "subs")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--skip-download",
            "-o", out_template,
            f"https://www.youtube.com/watch?v={video_id}",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

        # Find the downloaded VTT file
        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            return None

        return parse_vtt(vtt_files[0].read_text())


def parse_vtt(content: str) -> list[CaptionEntry]:
    """Parse WebVTT content into timed caption entries."""
    entries = []
    # Match timestamp lines: 00:00:47.366 --> 00:00:50.333
    # Followed by one or more text lines
    blocks = re.split(r"\n\n+", content)

    for block in blocks:
        lines = block.strip().split("\n")
        # Find the timestamp line
        for i, line in enumerate(lines):
            match = re.match(
                r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})",
                line,
            )
            if match:
                start = _parse_vtt_time(match.group(1))
                end = _parse_vtt_time(match.group(2))
                # Remaining lines are the text (strip size/position metadata from timestamp line)
                text_lines = lines[i + 1:]
                text = " ".join(t.strip() for t in text_lines if t.strip())
                # Remove music note markers and HTML tags
                text = re.sub(r"♪\s*", "", text)
                text = re.sub(r"<[^>]+>", "", text)
                text = text.strip()
                if text:
                    entries.append(CaptionEntry(start=start, end=end, text=text))
                break

    return entries


def _parse_vtt_time(time_str: str) -> float:
    """Parse HH:MM:SS.mmm to seconds."""
    parts = time_str.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _word_set(text: str) -> set[str]:
    """Get set of normalized words from text."""
    return set(_normalize(text).split())


@dataclass
class TimingMatch:
    start: float
    end: float
    caption_text: str
    matched_word: str
    confidence: str  # "high", "medium", "low"


def find_lyrics_timing(
    captions: list[CaptionEntry],
    post: RapWordsPost,
) -> list[TimingMatch]:
    """Find where the post's lyrics appear in the captions.

    Strategy:
    1. Search for the featured word(s) directly in captions — high confidence
    2. Search for multi-word phrases from the lyrics — medium confidence
    3. Sliding window word overlap — low confidence
    """
    matches: list[TimingMatch] = []
    featured_words = [w.word.lower() for w in post.words]
    lyrics_words = _word_set(" ".join(post.lyrics_lines))

    # Strategy 1: Direct featured word match
    for entry in captions:
        entry_normalized = _normalize(entry.text)
        for fw in featured_words:
            if fw in entry_normalized.split():
                matches.append(TimingMatch(
                    start=entry.start,
                    end=entry.end,
                    caption_text=entry.text,
                    matched_word=fw,
                    confidence="high",
                ))

    if matches:
        return matches

    # Strategy 2: Search for multi-word phrases from the lyrics (3+ consecutive words)
    for lyric_line in post.lyrics_lines:
        words = _normalize(lyric_line).split()
        for n in range(min(5, len(words)), 2, -1):  # try longer phrases first
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i + n])
                for entry in captions:
                    if phrase in _normalize(entry.text):
                        matches.append(TimingMatch(
                            start=entry.start,
                            end=entry.end,
                            caption_text=entry.text,
                            matched_word=phrase,
                            confidence="medium",
                        ))

    if matches:
        # Deduplicate by start time, prefer longer phrase matches
        seen_starts: set[float] = set()
        unique: list[TimingMatch] = []
        for m in matches:
            if m.start not in seen_starts:
                seen_starts.add(m.start)
                unique.append(m)
        return unique

    # Strategy 3: Sliding window word overlap
    for entry in captions:
        entry_words = _word_set(entry.text)
        overlap = lyrics_words & entry_words
        # Require at least 3 overlapping words to avoid false positives
        if len(overlap) >= 3:
            matches.append(TimingMatch(
                start=entry.start,
                end=entry.end,
                caption_text=entry.text,
                matched_word=", ".join(sorted(overlap)[:4]),
                confidence="low",
            ))

    return matches


def suggest_start_time(matches: list[TimingMatch], pre_roll: float = 3.0) -> float | None:
    """Given matches, suggest a start time with some pre-roll before the first match."""
    if not matches:
        return None
    # Use the earliest high-confidence match, or earliest of any
    best = min(matches, key=lambda m: ({"high": 0, "medium": 1, "low": 2}[m.confidence], m.start))
    return max(0, best.start - pre_roll)
