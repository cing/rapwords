"""Generate ASS subtitle files with karaoke-style word highlighting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rapwords.config import VIDEO_HEIGHT, VIDEO_WIDTH
from rapwords.models import RapWordsPost


@dataclass(frozen=True)
class LyricsTheme:
    name: str
    # Lyrics style colors (ASS &HAABBGGRR format)
    lyrics_primary: str      # Text color before karaoke fill (dimmed)
    lyrics_secondary: str    # Text color after karaoke fill (bright)
    lyrics_outline: str      # Box border color
    lyrics_back: str         # Box fill color
    # Featured word
    featured_color: str      # Featured word text color
    # WordDef style colors
    worddef_primary: str     # WordDef text color
    worddef_outline: str     # WordDef box border
    worddef_back: str        # WordDef box fill


THEMES: dict[str, LyricsTheme] = {
    "yellow": LyricsTheme(
        name="yellow",
        lyrics_primary="&H60000000",
        lyrics_secondary="&H00000000",
        lyrics_outline="&H0000D4FF",
        lyrics_back="&H0000D4FF",
        featured_color="&H00003AE0",
        worddef_primary="&H00FFFFFF",
        worddef_outline="&H00202020",
        worddef_back="&HC0000000",
    ),
    "pink": LyricsTheme(
        name="pink",
        lyrics_primary="&H60FFFFFF",
        lyrics_secondary="&H00FFFFFF",
        lyrics_outline="&H009933FF",
        lyrics_back="&H009933FF",
        featured_color="&H00EEFFFF",
        worddef_primary="&H00FFFFFF",
        worddef_outline="&H009933FF",
        worddef_back="&HC09933FF",
    ),
    "ice": LyricsTheme(
        name="ice",
        lyrics_primary="&H60000000",
        lyrics_secondary="&H00000000",
        lyrics_outline="&H00FFDDAA",
        lyrics_back="&H00FFDDAA",
        featured_color="&H00CC4400",
        worddef_primary="&H00FFFFFF",
        worddef_outline="&H00FFDDAA",
        worddef_back="&HC0FFDDAA",
    ),
}

DEFAULT_THEME = "yellow"


def _build_ass_header(theme: LyricsTheme) -> str:
    """Build the ASS header with styles based on the selected theme."""
    return f"""[Script Info]
Title: RapWords Karaoke
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: WordDef,Arial,44,{theme.worddef_primary},&H000000FF,{theme.worddef_outline},{theme.worddef_back},-1,0,0,0,100,100,1,0,3,10,0,8,60,60,60,1
Style: Lyrics,Arial,48,{theme.lyrics_primary},{theme.lyrics_secondary},{theme.lyrics_outline},{theme.lyrics_back},-1,0,0,0,100,100,2,0,3,12,0,2,80,80,300,1
Style: Attribution,Arial,36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,-1,0,0,100,100,0,0,1,2,1,2,40,40,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _format_time(seconds: float) -> str:
    """Format seconds as H:MM:SS.cc for ASS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _is_featured_word(word_text: str, featured_words: list[str]) -> bool:
    """Check if a word matches any featured word (case-insensitive, ignoring punctuation)."""
    clean = re.sub(r"[^a-zA-Z]", "", word_text).lower()
    return any(clean.startswith(fw) or fw.startswith(clean) for fw in featured_words if clean and fw)


def _estimate_syllables(word: str) -> int:
    """Rough syllable count for timing weight. Not linguistically perfect, but good enough."""
    word = re.sub(r"[^a-zA-Z]", "", word).lower()
    if not word:
        return 1
    # Count vowel groups
    count = len(re.findall(r"[aeiouy]+", word))
    # Adjust for silent e
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _distribute_time_by_syllables(words: list[str], total_time: float) -> list[int]:
    """Distribute time across words weighted by syllable count. Returns centiseconds per word."""
    syllables = [_estimate_syllables(w) for w in words]
    total_syllables = sum(syllables)
    if total_syllables == 0:
        cs = max(1, int(total_time * 100 / len(words)))
        return [cs] * len(words)
    return [max(1, int(total_time * 100 * s / total_syllables)) for s in syllables]


def generate_ass(
    post: RapWordsPost,
    clip_duration: float,
    line_timings: list | None = None,
    show_attribution: bool = False,
    theme: str = DEFAULT_THEME,
) -> str:
    """Generate ASS subtitle content with karaoke highlighting.

    Args:
        post: The post data with lyrics and featured words.
        clip_duration: Total clip duration in seconds.
        line_timings: Optional per-line timing from caption alignment.
            Each entry should have .line_start and .line_end (seconds from clip start).
            If None, falls back to equal division.
        theme: Color theme name ("yellow", "pink", or "ice").
    """
    resolved_theme = THEMES.get(theme, THEMES[DEFAULT_THEME])
    header = _build_ass_header(resolved_theme)

    lines = []
    lines.append(header.rstrip())

    featured_words = [w.word.lower() for w in post.words]

    # Word definition at top of screen — visible throughout
    word_defs = []
    for w in post.words:
        display_word = (w.syllables or w.word).upper()
        pos = w.part_of_speech.value
        defn = w.definition
        word_defs.append(f"{display_word}\\N{pos} — {defn}")

    def_text = "\\N\\N".join(word_defs)
    lines.append(
        f"Dialogue: 0,{_format_time(0.5)},{_format_time(clip_duration - 0.5)},WordDef,,0,0,0,,{def_text}"
    )

    # Lyrics with karaoke timing
    num_lines = len(post.lyrics_lines)
    if num_lines == 0:
        return "\n".join(lines) + "\n"

    # Determine per-line start/end times
    if line_timings and len(line_timings) == num_lines:
        # Use caption-aligned timing
        line_intervals = [(lt.line_start, lt.line_end) for lt in line_timings]
    else:
        # Fall back to equal division
        lyrics_start = 1.5
        lyrics_end = clip_duration - 1.0
        total_lyrics_time = lyrics_end - lyrics_start
        gap = 0.3
        total_gap = gap * (num_lines - 1) if num_lines > 1 else 0
        time_per_line = (total_lyrics_time - total_gap) / num_lines
        line_intervals = [
            (lyrics_start + i * (time_per_line + gap),
             lyrics_start + i * (time_per_line + gap) + time_per_line)
            for i in range(num_lines)
        ]

    first_line_start = line_intervals[0][0] if line_intervals else 1.5

    for i, lyric_line in enumerate(post.lyrics_lines):
        line_start, line_end = line_intervals[i]

        words_in_line = lyric_line.split()
        if not words_in_line:
            continue

        line_duration = line_end - line_start

        # Distribute time weighted by syllable count
        cs_per_word = _distribute_time_by_syllables(words_in_line, line_duration)

        # Build karaoke text with \kf (fill) tags
        karaoke_parts = []
        for j, word_text in enumerate(words_in_line):
            cs = cs_per_word[j]
            if _is_featured_word(word_text, featured_words):
                karaoke_parts.append(
                    f"{{\\kf{cs}\\c{resolved_theme.featured_color}\\2c{resolved_theme.featured_color}\\fs56}}{word_text}{{\\c\\2c\\fs}}"
                )
            else:
                karaoke_parts.append(f"{{\\kf{cs}}}{word_text}")

        # End each line when the next one starts (one line at a time)
        if i + 1 < len(line_intervals):
            display_end = line_intervals[i + 1][0]
        else:
            display_end = line_end + 1.0

        karaoke_text = " ".join(karaoke_parts)
        lines.append(
            f"Dialogue: 1,{_format_time(line_start)},{_format_time(display_end)},Lyrics,,0,0,0,,{karaoke_text}"
        )

    # Attribution at bottom (optional)
    if show_attribution:
        attr_text = f"— {post.artist} \"{post.song_title}\""
        lines.append(
            f"Dialogue: 0,{_format_time(first_line_start)},{_format_time(clip_duration - 0.5)},Attribution,,0,0,0,,{attr_text}"
        )

    return "\n".join(lines) + "\n"


def write_ass_file(
    post: RapWordsPost,
    clip_duration: float,
    output_path: Path,
    line_timings: list | None = None,
    show_attribution: bool = False,
    theme: str = DEFAULT_THEME,
) -> Path:
    """Generate and write an ASS subtitle file."""
    content = generate_ass(post, clip_duration, line_timings, show_attribution=show_attribution, theme=theme)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return output_path
