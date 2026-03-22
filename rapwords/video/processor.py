"""Process videos with ffmpeg — crop to 9:16, burn karaoke subtitles."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rapwords.config import DEFAULT_CLIP_DURATION, OUTPUT_DIR, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from rapwords.models import RapWordsPost
from rapwords.video.subtitles import write_ass_file


def process_post(post: RapWordsPost) -> str | None:
    """Process a post into an Instagram-ready video.

    Requires post.video_path, post.start_time, and post.duration to be set.
    Returns the output file path on success, None on failure.
    """
    if not post.video_path:
        print("No video file available.")
        return None

    video_path = Path(post.video_path)
    if not video_path.exists():
        print(f"Video file not found: {video_path}")
        return None

    start_time = post.start_time if post.start_time is not None else 0
    duration = post.duration or DEFAULT_CLIP_DURATION

    # Generate subtitle file
    word_slug = "_".join(w.word for w in post.words)[:30]
    ass_path = OUTPUT_DIR / f"{post.id}_{word_slug}.ass"
    write_ass_file(post, duration, ass_path)

    # Output path
    output_path = OUTPUT_DIR / f"{post.id}_{word_slug}.mp4"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build ffmpeg filter chain:
    # 1. Scale to fit width, maintaining aspect ratio
    # 2. Pad to 9:16 (center vertically with black bars)
    # 3. Slight darken for text readability
    # 4. Burn ASS subtitles
    ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    vf = (
        f"scale={VIDEO_WIDTH}:-2,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
        f"eq=brightness=-0.08,"
        f"ass='{ass_path_escaped}'"
    )

    cmd = [
        "ffmpeg",
        "-y",  # overwrite output
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-r", str(VIDEO_FPS),
        "-movflags", "+faststart",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
        else:
            if result.stderr:
                # Print last few lines of stderr for debugging
                stderr_lines = result.stderr.strip().split("\n")
                for line in stderr_lines[-10:]:
                    print(f"  ffmpeg: {line}")
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"ffmpeg error: {e}")
        return None
