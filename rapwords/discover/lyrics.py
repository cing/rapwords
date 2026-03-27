"""Fetch lyrics from Genius via the lyricsgenius library."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class SongResult:
    title: str
    artist: str
    lyrics: str
    genius_url: str | None = None
    release_year: int | None = None


def _patch_lyricsgenius():
    """Patch lyricsgenius's safe_unicode to not crash when sys.stdout.encoding is None."""
    import lyricsgenius.genius
    import lyricsgenius.types.artist
    import lyricsgenius.types.base
    import lyricsgenius.utils

    _safe = lambda s: s if isinstance(s, str) else str(s)
    for mod in (lyricsgenius.utils, lyricsgenius.genius,
                lyricsgenius.types.artist, lyricsgenius.types.base):
        if hasattr(mod, "safe_unicode"):
            mod.safe_unicode = _safe


def _get_genius():
    """Create a lyricsgenius client using GENIUS_API_TOKEN env var."""
    import logging

    import lyricsgenius

    _patch_lyricsgenius()
    logging.getLogger("lyricsgenius").setLevel(logging.WARNING)

    token = os.environ.get("GENIUS_API_TOKEN")
    if not token:
        raise RuntimeError(
            "Set GENIUS_API_TOKEN environment variable. "
            "Get a free token at https://genius.com/api-clients"
        )
    genius = lyricsgenius.Genius(token, remove_section_headers=True, timeout=30)
    genius.retries = 5
    return genius


def search_song(artist_name: str, song_title: str) -> SongResult | None:
    """Search for a specific song by artist and title. Returns lyrics or None."""
    genius = _get_genius()
    for attempt in range(3):
        try:
            song = genius.search_song(song_title, artist_name)
            break
        except Exception as e:
            if attempt < 2:
                wait = 5 * (attempt + 1)
                print(f"  Timeout, retrying in {wait}s... ({e.__class__.__name__})")
                time.sleep(wait)
            else:
                print(f"  Failed after 3 attempts: {e}")
                return None
    if not song or not song.lyrics:
        return None
    return SongResult(
        title=song.title,
        artist=song.artist,
        lyrics=song.lyrics,
        genius_url=song.url,
        release_year=_extract_year(song),
    )


def search_artist_songs(
    artist_name: str,
    max_songs: int = 20,
) -> list[SongResult]:
    """Fetch songs for an artist from Genius. Returns list of SongResults with lyrics."""
    genius = _get_genius()
    for attempt in range(3):
        try:
            artist = genius.search_artist(artist_name, max_songs=max_songs, sort="popularity")
            break
        except Exception as e:
            if attempt < 2:
                wait = 5 * (attempt + 1)
                print(f"  Timeout, retrying in {wait}s... ({e.__class__.__name__})")
                time.sleep(wait)
            else:
                print(f"  Failed after 3 attempts: {e}")
                return []
    else:
        return []
    if not artist:
        return []

    results = []
    for song in artist.songs:
        if song.lyrics:
            results.append(SongResult(
                title=song.title,
                artist=song.artist,
                lyrics=song.lyrics,
                genius_url=song.url,
                release_year=_extract_year(song),
            ))
    return results



def _extract_year(song) -> int | None:
    """Extract release year from a lyricsgenius Song object."""
    try:
        data = song.to_dict()
        components = data.get("release_date_components")
        if components and components.get("year"):
            return int(components["year"])
        release_date = data.get("release_date", "")
        if release_date and len(release_date) >= 4:
            return int(release_date[:4])
    except Exception:
        pass
    return None
