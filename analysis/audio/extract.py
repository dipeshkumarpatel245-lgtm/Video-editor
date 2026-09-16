"""Extract audio as mono WAV at working sample rate.

Videos without an audio stream yield a silent WAV of the right duration so the
rest of the audio analysis can run on a well-formed file instead of crashing.
"""
from __future__ import annotations
from pathlib import Path
import wave

from config import FFMPEG, FFPROBE, SAMPLE_RATE, MEDIA_DIR
from ffutils import run_ffmpeg, run


def _has_audio(video_path: str) -> bool:
    try:
        cp = run([FFPROBE, "-v", "quiet", "-select_streams", "a",
                  "-show_entries", "stream=index", "-of", "csv=p=0", video_path])
        return bool(cp.stdout.strip())
    except Exception:
        return False


def _duration(video_path: str) -> float:
    try:
        cp = run([FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
                  "-of", "csv=p=0", video_path])
        return float(cp.stdout.strip().splitlines()[0])
    except Exception:
        return 0.0


def _silent_wav(out_wav: Path, seconds: float) -> None:
    n = max(1, int(seconds * SAMPLE_RATE))
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * n)


def extract_audio(input_video: str, out_dir: str | Path | None = None) -> str:
    out_dir = Path(out_dir or MEDIA_DIR / "audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_video).stem
    out_wav = Path(out_dir) / f"{stem}.wav"
    if not _has_audio(input_video):
        _silent_wav(out_wav, _duration(input_video))
        return str(out_wav)
    run_ffmpeg(
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-acodec", "pcm_s16le",
        "-y", str(out_wav),
        input_file=input_video,
    )
    return str(out_wav)