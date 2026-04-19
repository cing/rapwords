"""Search YouTube for official music videos using yt-dlp, with ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class YouTubeResult:
    video_id: str
    url: str
    title: str
    channel: str = ""
    view_count: int = 0
    score: int = 0
    alternatives: list["YouTubeResult"] = field(default_factory=list)


# Scoring signals. "Live" only counts if nothing in the set has an "official" hint.
_OFFICIAL_TITLE_PATTERNS = (
    "official video",
    "official music video",
    "official audio",  # keep mildly positive — better than bootleg
)
_LIVE_TITLE_PATTERNS = (
    "live",
    "performance",
    "tiny desk",
    "live session",
)
_NEGATIVE_TITLE_PATTERNS = (
    ("lyric video", -2),
    ("lyrics", -2),
    ("visualizer", -2),
    ("audio only", -2),
    ("reaction", -4),
    ("cover", -4),
    ("remix", -4),
    ("sped up", -3),
    ("slowed", -3),
)

# Words that show up in titles but don't help disambiguate which *song version*
# we have. Stripped from both the searched title and the candidate title.
_TITLE_STOPWORDS = frozenset({
    "the", "and", "for", "feat", "ft", "featuring", "with", "official",
    "music", "video", "audio", "version", "hd", "hq", "lyrics", "explicit",
    "clean", "dirty", "a", "an", "of", "to",
})


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _title_tokens(song_title: str) -> tuple[frozenset[str], frozenset[str]]:
    """Split a song title into (base_tokens, qualifier_tokens).

    Qualifier tokens live after the first ``(``/``[``/``-``/dash — they mark
    the specific version ("Ladies Night Remix", "Live at Wembley", etc.).
    Base tokens are the song's primary name. Stopwords are dropped from both.
    """
    # Find first delimiter that opens a qualifier section
    base_part = song_title
    qual_part = ""
    for i, ch in enumerate(song_title):
        if ch in "([-\u2013\u2014":  # ( [ - en-dash em-dash
            base_part = song_title[:i]
            qual_part = song_title[i:]
            break

    def _toks(s: str) -> frozenset[str]:
        return frozenset(
            t for t in re.findall(r"[a-z]+", s.lower())
            if len(t) > 2 and t not in _TITLE_STOPWORDS
        )

    return _toks(base_part), _toks(qual_part)


def _score_entry(
    entry: dict,
    artist: str,
    song_title: str,
    has_any_official: bool,
    base_tokens: frozenset[str],
    qualifier_tokens: frozenset[str],
) -> int:
    title = (entry.get("title") or "").lower()
    channel = (entry.get("channel") or entry.get("uploader") or "").lower()
    score = 0

    if "vevo" in channel:
        score += 5

    artist_norm = _normalize(artist)
    if artist_norm and artist_norm in _normalize(channel):
        score += 3

    if any(p in title for p in _OFFICIAL_TITLE_PATTERNS):
        score += 3
    elif not has_any_official and any(p in title for p in _LIVE_TITLE_PATTERNS):
        score += 2

    view_count = entry.get("view_count") or 0
    if isinstance(view_count, (int, float)) and view_count >= 1_000_000:
        score += 1

    # Qualifier match: if the searched song title carries a qualifier like
    # "(Ladies Night Remix)" we strongly prefer candidates whose title carries
    # the same qualifier tokens. Without this, YouTube usually returns the
    # more-popular base-version and the scorer can't tell they're different
    # songs. Implemented as a range: full match = big reward, no match = big
    # penalty, partial = small reward.
    if qualifier_tokens:
        matched = sum(1 for t in qualifier_tokens if t in title)
        ratio = matched / len(qualifier_tokens)
        if ratio == 1.0:
            score += 5
        elif ratio >= 0.5:
            score += 2
        else:
            score -= 5

    # Negative title keywords. If the searched song *is* a remix/cover, those
    # words are expected in the candidate — skip the penalty for them.
    for pattern, delta in _NEGATIVE_TITLE_PATTERNS:
        if pattern not in title:
            continue
        if pattern in qualifier_tokens or pattern in " ".join(qualifier_tokens):
            continue
        if pattern == "remix" and artist_norm and artist_norm in _normalize(channel):
            continue
        score += delta

    return score


def _entry_to_result(entry: dict, score: int) -> YouTubeResult | None:
    video_id = entry.get("id")
    if not video_id:
        return None
    return YouTubeResult(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=entry.get("title", ""),
        channel=entry.get("channel") or entry.get("uploader") or "",
        view_count=entry.get("view_count") or 0,
        score=score,
    )


def find_youtube_video(
    artist: str,
    song_title: str,
    max_results: int = 5,
) -> YouTubeResult | None:
    """Search YouTube and return the highest-scoring match for artist + song.

    Fetches up to `max_results` candidates, scores each on official-video /
    live-performance / channel signals, and returns the best. The returned
    result carries its score and the runners-up in `alternatives` (already
    sorted best-to-worst, excluding the chosen one).
    """
    query = f"{artist} {song_title} official music video"

    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)

        if not result or "entries" not in result or not result["entries"]:
            return None

        entries = [e for e in result["entries"] if e and e.get("id")]
        if not entries:
            return None

        has_any_official = any(
            any(p in (e.get("title") or "").lower() for p in _OFFICIAL_TITLE_PATTERNS)
            or "vevo" in (e.get("channel") or e.get("uploader") or "").lower()
            for e in entries
        )

        base_tokens, qualifier_tokens = _title_tokens(song_title)

        scored: list[tuple[int, int, YouTubeResult]] = []
        for idx, entry in enumerate(entries):
            s = _score_entry(
                entry, artist, song_title, has_any_official,
                base_tokens, qualifier_tokens,
            )
            r = _entry_to_result(entry, s)
            if r is None:
                continue
            # Tie-break: higher score, then higher view count, then original order
            scored.append((s, r.view_count, r))

        if not scored:
            return None

        scored.sort(key=lambda t: (-t[0], -t[1]))
        best = scored[0][2]
        best.alternatives = [t[2] for t in scored[1:]]
        return best
    except Exception:
        return None
