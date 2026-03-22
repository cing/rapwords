"""Process videos with ffmpeg — crop to 9:16, burn karaoke subtitles."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rapwords.config import (
    DEFAULT_CLIP_DURATION,
    OUTPUT_DIR,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    WATERMARK_BLACK,
    WATERMARK_OPACITY,
    WATERMARK_PADDING,
    WATERMARK_WHITE,
)
from rapwords.models import RapWordsPost
from rapwords.video.subtitles import write_ass_file


def process_post(
    post: RapWordsPost,
    crop: bool = True,
    show_attribution: bool = False,
    watermark: str = "white",
) -> str | None:
    """Process a post into an Instagram-ready video.

    Requires post.video_path, post.start_time, and post.duration to be set.

    Args:
        crop: If True (default), scale to fill and center-crop to 9:16.
              If False, scale to fit and pad with black bars.
        watermark: "white", "black", or "none".
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

    # Try to get per-line timing from YouTube captions
    line_timings = None
    if post.youtube_video_id:
        try:
            from rapwords.video.captions import align_lyrics_to_captions, download_captions
            captions = download_captions(post.youtube_video_id)
            if captions:
                line_timings = align_lyrics_to_captions(
                    captions, post, start_time, duration,
                )
                if line_timings:
                    print(f"  Synced to captions ({len(line_timings)} lines aligned)")
                else:
                    print("  Captions available but alignment failed, using syllable-weighted timing")
            else:
                print("  No captions, using syllable-weighted timing")
        except Exception:
            print("  Caption sync skipped, using syllable-weighted timing")

    # Generate subtitle file
    word_slug = "_".join(w.word for w in post.words)[:30]
    ass_path = OUTPUT_DIR / f"{post.id}_{word_slug}.ass"
    write_ass_file(post, duration, ass_path, line_timings=line_timings, show_attribution=show_attribution)

    # Output path
    output_path = OUTPUT_DIR / f"{post.id}_{word_slug}.mp4"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve watermark path
    watermark_path = None
    if watermark == "white" and WATERMARK_WHITE.exists():
        watermark_path = WATERMARK_WHITE
    elif watermark == "black" and WATERMARK_BLACK.exists():
        watermark_path = WATERMARK_BLACK

    # Build ffmpeg filter chain
    ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    if crop:
        base_vf = (
            f"scale=-2:{VIDEO_HEIGHT},"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"eq=brightness=-0.08,"
            f"ass='{ass_path_escaped}'"
        )
    else:
        base_vf = (
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
    ]

    if watermark_path:
        cmd.extend(["-i", str(watermark_path)])
        # filter_complex: process video, then overlay watermark with reduced opacity
        pad = WATERMARK_PADDING
        fc = (
            f"[0:v]{base_vf}[vid];"
            f"[1:v]format=rgba,colorchannelmixer=aa={WATERMARK_OPACITY}[wm];"
            f"[vid][wm]overlay=W-w-{pad}:H-h-{pad}[out]"
        )
        cmd.extend(["-filter_complex", fc, "-map", "[out]", "-map", "0:a?"])
    else:
        cmd.extend(["-vf", base_vf])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-r", str(VIDEO_FPS),
        "-movflags", "+faststart",
        str(output_path),
    ])

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
