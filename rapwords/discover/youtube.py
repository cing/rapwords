"""Search YouTube for official music videos using yt-dlp."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass
class YouTubeResult:
    video_id: str
    url: str
    title: str


def find_youtube_video(artist: str, song_title: str) -> YouTubeResult | None:
    """Search YouTube for an official music video. Returns the top result."""
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
            result = ydl.extract_info(f"ytsearch1:{query}", download=False)

        if not result or "entries" not in result or not result["entries"]:
            return None

        entry = result["entries"][0]
        video_id = entry.get("id")
        title = entry.get("title", "")

        if not video_id:
            return None

        return YouTubeResult(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=title,
        )
    except Exception:
        return None
