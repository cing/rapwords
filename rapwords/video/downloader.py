"""Download YouTube videos using yt-dlp."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rapwords.config import VIDEOS_DIR
from rapwords.models import RapWordsPost


def _video_path(post: RapWordsPost) -> Path:
    return VIDEOS_DIR / f"{post.id}_{post.youtube_video_id}.mp4"


def download_video(
    post: RapWordsPost,
    cookies_from_browser: str | None = None,
) -> str | None:
    """Download the YouTube video for a post. Returns the file path on success.

    Args:
        cookies_from_browser: Browser name to extract cookies from (e.g. "chrome",
            "firefox", "brave", "edge"). Needed for age-restricted or login-gated videos.
    """
    if not post.youtube_video_id:
        return None

    output_path = _video_path(post)

    # Skip if already downloaded
    if output_path.exists():
        return str(output_path)

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={post.youtube_video_id}"

    import sys
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(output_path),
        "--no-playlist",
        "--no-overwrites",
    ]

    if cookies_from_browser:
        cmd.extend(["--cookies-from-browser", cookies_from_browser])

    cmd.append(url)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
        else:
            # Print error for debugging
            if result.stderr:
                print(f"yt-dlp error: {result.stderr[:500]}")
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Download error: {e}")
        return None
