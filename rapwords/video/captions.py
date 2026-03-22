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


def _match_line_to_captions(
    lyric_line: str,
    captions: list[CaptionEntry],
    featured_words: list[str],
) -> TimingMatch | None:
    """Find the best caption match for a single lyrics line."""
    line_words = _normalize(lyric_line).split()
    if not line_words:
        return None

    best: TimingMatch | None = None
    best_score = 0

    for entry in captions:
        entry_norm = _normalize(entry.text)
        entry_word_list = entry_norm.split()
        entry_word_set = set(entry_word_list)
        line_word_set = set(line_words)

        overlap = line_word_set & entry_word_set
        score = len(overlap) / len(line_word_set)

        if score <= best_score:
            continue

        # Determine confidence
        has_featured = any(fw in entry_word_list for fw in featured_words)
        if has_featured and score >= 0.4:
            confidence = "high"
        elif score >= 0.5:
            confidence = "medium"
        elif score >= 0.3:
            confidence = "low"
        else:
            continue

        matched_word = next(
            (fw for fw in featured_words if fw in entry_word_list),
            ", ".join(sorted(overlap)[:3]),
        )
        best = TimingMatch(
            start=entry.start,
            end=entry.end,
            caption_text=entry.text,
            matched_word=matched_word,
            confidence=confidence,
        )
        best_score = score

    return best


def find_lyrics_timing(
    captions: list[CaptionEntry],
    post: RapWordsPost,
) -> list[TimingMatch]:
    """Find where each lyrics line appears in the captions.

    Matches every lyrics line independently to its best caption entry,
    so the results cover the full span from first to last line.
    """
    featured_words = [w.word.lower() for w in post.words]
    matches: list[TimingMatch] = []
    seen_starts: set[float] = set()

    for lyric_line in post.lyrics_lines:
        m = _match_line_to_captions(lyric_line, captions, featured_words)
        if m and m.start not in seen_starts:
            matches.append(m)
            seen_starts.add(m.start)

    # Sort by time
    matches.sort(key=lambda m: m.start)
    return matches


@dataclass
class LineTiming:
    """Timing for a single lyrics line, relative to clip start."""
    line_start: float  # seconds from clip start
    line_end: float
    text: str


def align_lyrics_to_captions(
    captions: list[CaptionEntry],
    post: RapWordsPost,
    clip_start: float,
    clip_duration: float,
) -> list[LineTiming] | None:
    """Match each lyrics line to caption entries and return per-line timing.

    Args:
        captions: All caption entries with absolute timestamps.
        clip_start: The absolute start time of the clip in the video.
        clip_duration: Duration of the clip.

    Returns:
        A list of LineTiming (one per lyrics line) with times relative to
        clip start, or None if alignment fails.
    """
    if not captions or not post.lyrics_lines:
        return None

    clip_end = clip_start + clip_duration
    timings: list[LineTiming] = []

    for lyric_line in post.lyrics_lines:
        lyric_words = set(_normalize(lyric_line).split())
        if not lyric_words:
            continue

        # Score each caption entry by word overlap with this lyrics line
        best_score = 0
        best_entry: CaptionEntry | None = None

        for entry in captions:
            # Only consider entries that overlap with the clip window
            if entry.end < clip_start or entry.start > clip_end:
                continue
            caption_words = set(_normalize(entry.text).split())
            overlap = len(lyric_words & caption_words)
            # Normalize by the size of the lyrics line to prefer precise matches
            score = overlap / len(lyric_words) if lyric_words else 0
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= 0.3:
            # Convert absolute time to clip-relative time
            rel_start = max(0, best_entry.start - clip_start)
            rel_end = max(rel_start + 0.5, min(clip_duration, best_entry.end - clip_start))
            timings.append(LineTiming(
                line_start=rel_start,
                line_end=rel_end,
                text=lyric_line,
            ))
        else:
            # No good match — return None to fall back to equal division
            return None

    # Validate: timings should be roughly sequential
    for i in range(1, len(timings)):
        if timings[i].line_start < timings[i - 1].line_start - 1.0:
            # Out of order by more than 1s — alignment is probably wrong
            return None

    return timings


@dataclass
class SuggestedTiming:
    start: float  # suggested start time (absolute, in seconds)
    duration: float  # suggested clip duration


def suggest_timing(
    matches: list[TimingMatch],
    pre_roll: float = 3.0,
    post_roll: float = 2.0,
    min_duration: float = 10.0,
) -> SuggestedTiming | None:
    """Suggest start time and duration that covers all matched lyrics.

    Uses the earliest and latest matches to compute the span, then adds
    pre-roll before and post-roll after.
    """
    if not matches:
        return None

    earliest = min(matches, key=lambda m: m.start)
    latest = max(matches, key=lambda m: m.end)

    start = max(0, earliest.start - pre_roll)
    end = latest.end + post_roll
    duration = max(min_duration, end - start)

    return SuggestedTiming(start=start, duration=duration)
