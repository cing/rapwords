"""Fetch lyrics from Genius via the lyricsgenius library."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SongResult:
    title: str
    artist: str
    lyrics: str
    genius_url: str | None = None


def _get_genius():
    """Create a lyricsgenius client using GENIUS_API_TOKEN env var."""
    import lyricsgenius

    token = os.environ.get("GENIUS_API_TOKEN")
    if not token:
        raise RuntimeError(
            "Set GENIUS_API_TOKEN environment variable. "
            "Get a free token at https://genius.com/api-clients"
        )
    genius = lyricsgenius.Genius(token, verbose=False, remove_section_headers=True)
    genius.retries = 3
    return genius


def search_song(artist_name: str, song_title: str) -> SongResult | None:
    """Search for a specific song by artist and title. Returns lyrics or None."""
    genius = _get_genius()
    song = genius.search_song(song_title, artist_name)
    if not song or not song.lyrics:
        return None
    return SongResult(
        title=song.title,
        artist=song.artist,
        lyrics=song.lyrics,
        genius_url=song.url,
    )


def search_artist_songs(
    artist_name: str,
    max_songs: int = 20,
) -> list[SongResult]:
    """Fetch songs for an artist from Genius. Returns list of SongResults with lyrics."""
    genius = _get_genius()
    artist = genius.search_artist(artist_name, max_songs=max_songs, sort="popularity")
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
            ))
    return results
