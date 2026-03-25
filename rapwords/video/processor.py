"""Process videos with ffmpeg — crop to 9:16, burn karaoke subtitles."""

from __future__ import annotations

import random
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

STATIC_DURATION = 0.75  # seconds of static after hard cut
STATIC_ASSET = Path(__file__).parent.parent / "assets" / "tv_static.mp4"


def _add_static_outro(input_path: Path, output_path: Path) -> bool:
    """Append an abrupt hard cut to TV static at the end of a video.

    Uses a real TV static video asset with generated white noise audio.
    The cut is instant — like someone changed the channel.
    """
    if not STATIC_ASSET.exists():
        return False

    # Prepare a static segment scaled to match output dimensions,
    # replacing the asset's audio with generated white noise
    static_segment = input_path.with_suffix(".static_seg.mp4")
    # Random seek into the asset for variety each time
    seek = round(random.uniform(0.5, 5.0), 2)
    cmd_static = [
        "ffmpeg", "-y",
        "-ss", str(seek),
        "-t", str(STATIC_DURATION),
        "-i", str(STATIC_ASSET),
        "-f", "lavfi",
        "-t", str(STATIC_DURATION),
        "-i", f"anoisesrc=color=white:sample_rate=44100:amplitude=0.5",
        "-filter_complex",
        f"[0:v]scale=-2:{VIDEO_HEIGHT},crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={VIDEO_FPS}[v];"
        f"[1:a]aformat=channel_layouts=stereo[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-r", str(VIDEO_FPS),
        str(static_segment),
    ]
    result = subprocess.run(cmd_static, capture_output=True, text=True, timeout=30)
    if result.returncode != 0 or not static_segment.exists():
        return False

    # Concat via filter for reliable joining
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-i", str(static_segment),
            "-filter_complex",
            "[0:v]setsar=1[v0];[1:v]setsar=1[v1];"
            "[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[vout][aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return result.returncode == 0 and output_path.exists()
    finally:
        static_segment.unlink(missing_ok=True)


def process_post(
    post: RapWordsPost,
    crop: bool = True,
    crop_offset: int = 0,
    show_attribution: bool = False,
    watermark: str = "white",
    watermark_scale: float = 0.7,
    theme: str = "yellow",
    static: bool = True,
    ass_file: str | None = None,
    use_align: bool = True,
) -> str | None:
    """Process a post into an Instagram-ready video.

    Requires post.video_path, post.start_time, and post.duration to be set.

    Args:
        crop: If True (default), scale to fill and center-crop to 9:16.
              If False, scale to fit and pad with black bars.
        watermark: "white", "black", or "none".
        static: If True (default), add TV static outro effect.
        ass_file: Path to an existing .ass subtitle file. If provided,
                  skips subtitle generation and uses this file instead.
        use_align: If True (default), use whisperX for word-level timing.
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

    word_slug = "_".join(w.word for w in post.words)[:30]

    if ass_file:
        ass_path = Path(ass_file)
        if not ass_path.exists():
            print(f"ASS file not found: {ass_path}")
            return None
        print(f"  Using existing subtitle file: {ass_path}")
    else:
        # Try to get per-line timing, with word-level alignment
        # Priority: 1) whisperX forced alignment, 2) YouTube captions, 3) syllable estimation
        line_timings = None

        # Try whisperX alignment first (gives word-level timing)
        if use_align:
            try:
                from rapwords.video.align import align_lyrics
                line_timings = align_lyrics(
                    post.video_path, post.lyrics_lines, start_time, duration,
                )
                if line_timings:
                    word_count = sum(len(lt.words) for lt in line_timings)
                    print(f"  whisperX aligned {word_count} words across {len(line_timings)} lines")
            except Exception as e:
                print(f"  whisperX skipped: {e}")

        # Fall back to YouTube captions for line-level timing
        if not line_timings and post.youtube_video_id:
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
        ass_path = OUTPUT_DIR / f"{post.id}_{word_slug}.ass"
        write_ass_file(post, duration, ass_path, line_timings=line_timings, show_attribution=show_attribution, theme=theme)

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
        crop_x = f"(iw-{VIDEO_WIDTH})/2+{crop_offset}" if crop_offset else ""
        crop_expr = f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}:{crop_x}" if crop_x else f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
        base_vf = (
            f"scale=-2:{VIDEO_HEIGHT},"
            f"{crop_expr},"
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

    # Render to temp file if static outro is needed, otherwise directly to output
    render_path = output_path.with_suffix(".tmp.mp4") if static else output_path

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
            f"[1:v]format=rgba,"
            f"scale=iw*{watermark_scale}:ih*{watermark_scale},"
            f"colorchannelmixer=aa={WATERMARK_OPACITY}[wm];"
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
        str(render_path),
    ])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0 or not render_path.exists():
            if result.stderr:
                stderr_lines = result.stderr.strip().split("\n")
                for line in stderr_lines[-10:]:
                    print(f"  ffmpeg: {line}")
            return None

        # Add static outro if requested
        if static:
            print("  Adding TV static outro...")
            if _add_static_outro(render_path, output_path):
                render_path.unlink(missing_ok=True)
                return str(output_path)
            else:
                # Fall back to the version without static
                print("  Static effect failed, using video without it")
                render_path.rename(output_path)
                return str(output_path)

        return str(output_path)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"ffmpeg error: {e}")
        return None
