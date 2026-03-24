"""Word-level audio alignment using whisperX forced alignment."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WordTiming:
    word: str
    start: float  # seconds
    end: float    # seconds
    score: float = 0.0


@dataclass
class LineTiming:
    text: str
    line_start: float
    line_end: float
    words: list[WordTiming] = field(default_factory=list)


def align_lyrics(
    video_path: str,
    lyrics_lines: list[str],
    start_time: float,
    duration: float,
    model_size: str = "base",
) -> list[LineTiming] | None:
    """Align lyrics to audio using whisperX forced alignment.

    Extracts audio from the video clip, runs whisperX with the known lyrics
    text, and returns per-word timestamps for each line.

    Args:
        video_path: Path to the source video file.
        lyrics_lines: The lyrics lines to align.
        start_time: Start time in the video (seconds).
        duration: Clip duration (seconds).
        model_size: Whisper model size ("tiny", "base", "small", "medium").

    Returns:
        List of LineTiming with per-word timestamps, or None on failure.
    """
    # Suppress noisy warnings from torch/pyannote/torchcodec/lightning before import
    import logging
    import warnings
    warnings.filterwarnings("ignore")
    for name in ("whisperx", "pyannote", "lightning", "lightning.pytorch",
                 "faster_whisper", "torch", "torchcodec", "torchvision"):
        logging.getLogger(name).setLevel(logging.ERROR)

    try:
        import whisperx
    except ImportError:
        print("  whisperX not installed. Install with: pip install whisperx")
        return None

    video = Path(video_path)
    if not video.exists():
        return None

    # Extract audio clip from video
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", str(video),
                "-vn",  # no video
                "-ac", "1",  # mono
                "-ar", "16000",  # 16kHz for whisper
                "-acodec", "pcm_s16le",
                audio_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print("  Failed to extract audio from video")
            return None

        # Load audio
        audio = whisperx.load_audio(audio_path)

        # Transcribe first to get segments (required for alignment)
        device = "cpu"
        compute_type = "int8"

        print(f"  Loading whisperX model ({model_size})...")
        model = whisperx.load_model(
            model_size, device=device, compute_type=compute_type, language="en",
        )

        # Create segments from our known lyrics rather than transcribing blindly
        # We transcribe to get rough timing, then align with our known text
        full_text = " ".join(lyrics_lines)

        # Use a single segment spanning the full clip with our lyrics
        segments = [{"start": 0.0, "end": duration, "text": full_text}]

        # Load alignment model and align
        print("  Aligning lyrics to audio...")
        align_model, metadata = whisperx.load_align_model(
            language_code="en", device=device,
        )
        aligned = whisperx.align(
            segments, align_model, metadata, audio, device=device,
        )

        # Extract word-level timings
        word_segments = aligned.get("word_segments", [])
        if not word_segments:
            print("  Alignment produced no word timings")
            return None

        # Map aligned words back to our lyrics lines
        return _map_words_to_lines(lyrics_lines, word_segments, duration)

    except Exception as e:
        print(f"  whisperX alignment failed: {e}")
        return None
    finally:
        Path(audio_path).unlink(missing_ok=True)


def _map_words_to_lines(
    lyrics_lines: list[str],
    word_segments: list[dict],
    duration: float,
) -> list[LineTiming]:
    """Map whisperX word segments back to the original lyrics lines."""
    import re

    # Flatten lyrics into words with line indices
    line_words: list[tuple[int, str]] = []
    for i, line in enumerate(lyrics_lines):
        for word in line.split():
            # Clean word for matching (strip punctuation)
            line_words.append((i, word))

    # Try to match aligned words to lyrics words in order
    line_timings: dict[int, LineTiming] = {}
    for i, line in enumerate(lyrics_lines):
        line_timings[i] = LineTiming(text=line, line_start=0.0, line_end=0.0)

    seg_idx = 0
    for line_idx, orig_word in line_words:
        if seg_idx >= len(word_segments):
            break

        seg = word_segments[seg_idx]
        seg_word = seg.get("word", "")
        start = seg.get("start")
        end = seg.get("end")
        score = seg.get("score", 0.0)

        # Skip segments without timing
        if start is None or end is None:
            seg_idx += 1
            continue

        wt = WordTiming(word=orig_word, start=start, end=end, score=score)
        lt = line_timings[line_idx]
        lt.words.append(wt)

        # Update line start/end
        if lt.line_start == 0.0 or start < lt.line_start:
            lt.line_start = start
        if end > lt.line_end:
            lt.line_end = end

        seg_idx += 1

    # Fill in missing line timings with estimates
    result = list(line_timings.values())
    _fill_gaps(result, duration)

    return result


def _fill_gaps(line_timings: list[LineTiming], duration: float):
    """Fill in any lines that got no alignment with estimated times."""
    # Find lines with no timing
    for i, lt in enumerate(line_timings):
        if lt.line_start == 0.0 and lt.line_end == 0.0 and not lt.words:
            # Estimate from surrounding lines
            prev_end = line_timings[i - 1].line_end if i > 0 else 0.5
            next_start = duration - 0.5
            for j in range(i + 1, len(line_timings)):
                if line_timings[j].line_start > 0:
                    next_start = line_timings[j].line_start
                    break
            lt.line_start = prev_end + 0.1
            lt.line_end = next_start - 0.1
