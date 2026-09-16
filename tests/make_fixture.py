"""Generate synthetic "template-like" videos to exercise the pipeline (no real footage needed)."""
from __future__ import annotations
import subprocess, shlex, os
import numpy as np
from scipy.io import wavfile


def make_clip(path: str, duration: float = 6.0, color: tuple = (40, 90, 200),
              motion: bool = True, fps: int = 30, w: int = 720, h: int = 404,
              pattern: str = "gradient") -> None:
    """A moving clip with a distinct color cast."""
    probe = f"tests/tmp_{os.path.basename(path).split('.')[0]}.yuv"
    n = int(duration * fps)
    fw, fh = w, h
    frames = np.zeros((n, fh, fw, 3), dtype=np.uint8)
    c = np.array(color, dtype=np.float32)
    for i in range(n):
        t = i / fps
        img = frames[i]
        if pattern == "gradient":
            xx = np.linspace(0, 1, fw, dtype=np.float32)
            base = (c[None, :] * xx[:, None]).astype(np.float32)
            wave = np.sin(2 * np.pi * (0.5 + 0.3 * t)) * 0.25 + 0.75
            img[:] = np.clip(base * wave, 0, 255).astype(np.uint8)
        elif pattern == "pulse":
            v = int(90 + 160 * abs(np.sin(2 * np.pi * t * 2.0)))
            img[:] = (np.clip(c + v, 0, 255)).astype(np.uint8)
        else:  # bars
            xx = np.arange(fw, dtype=np.float32)
            bar = (np.sin(xx * 0.05 + t * 3).reshape(1, fw, 1))
            img[:] = np.clip(c[None, None, :] * (bar[..., :] + 1.2) * 0.6, 0, 255).astype(np.uint8)
    frames.tofile(probe)
    vf = f"format=yuv420p,fps={fps}"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{fw}x{fh}", "-r", str(fps), "-i", probe,
           "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", path]
    subprocess.run(cmd, check=True)
    os.remove(probe)


def make_beats_audio(path: str, duration: float, bpm: float = 120.0,
                     sr: int = 22050, impact_at: list[float] | None = None) -> None:
    """Mono wav with a kick impulse per beat + extra impacts."""
    n = int(duration * sr)
    audio = np.zeros(n, dtype=np.float64)
    beat_sec = 60.0 / bpm
    e = 0
    t = 0.0
    while t < duration:
        i = int(t * sr)
        if 0 <= i < n:
            burst = np.exp(-np.linspace(0, 12, int(0.03 * sr))) * np.sin(
                2 * np.pi * 60 * np.linspace(0, 1, int(0.03 * sr)))
            end = min(n, i + len(burst))
            audio[i:end] += burst[:end - i] * 0.8
        t += beat_sec
        e += 1
    for ai in impact_at or []:
        i = int(ai * sr)
        if 0 <= i < n:
            burst = np.exp(-np.linspace(0, 8, int(0.10 * sr))) * np.sin(
                2 * np.pi * 90 * np.linspace(0, 1, int(0.10 * sr)))
            end = min(n, i + len(burst))
            audio[i:end] += burst[:end - i] * 3.2
    audio = np.clip(audio, -1, 1)
    wavfile.write(path, sr, (audio * 32767).astype(np.int16))


def make_template_video(path: str, shots: list[tuple[float, tuple]], duration: float = 25.0,
                        bpm: float = 120.0, flash_at: list[float] | None = None,
                        w: int = 720, h: int = 404, fps: int = 30) -> None:
    """Build a videosource with cuts [+ dissolves via crossfade] + flashes merged with beats audio."""
    # build per-shot clips
    parts = {}
    for i, (dur, color) in enumerate(shots):
        cpath = f"tests/tmp_shot{i}.mp4"
        make_clip(cpath, dur, color=color, pattern="pulse" if i % 2 else "gradient", fps=fps, w=w, h=h)
        parts[i] = cpath
    # concat with forced cut points (short black between) -> clear scene changes
    # simpler: hardcuts concatenation is fine
    lst = "tests/concat_list.txt"
    with open(lst, "w") as f:
        for i in range(len(shots)):
            f.write(f"file '{os.path.abspath(parts[i])}'\n")
    concat = "tests/tmp_silent.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", lst,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", concat], check=True)

    # flash effect: 3-frame white overlays at flash_at
    vf = "null"
    ff = "fps=30"
    for ft in flash_at or []:
        ff += f",drawbox=x=0:y=0:w=iw:h=ih:color=white@1:t=fill:enable='between(t,{ft},{ft+0.07})'"
    flash_path = "tests/tmp_flash.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", concat, "-vf", ff, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    flash_path], check=True)

    wav = "tests/tmp_beats.wav"
    make_beats_audio(wav, duration, bpm=bpm, impact_at=flash_at)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", flash_path, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-shortest", path], check=True)

    for p in parts.values():
        os.remove(p)
    os.remove(lst)
    os.remove(concat)
    os.remove(flash_path)
    os.remove(wav)


def make_fixture(out_dir: str) -> dict:
    """Generate (or reuse existing) synthetic source + custom clips.

    Returns {"source": path, "clips": [paths...]}.
    """
    out_dir = os.fspath(out_dir)
    source = os.path.join(out_dir, "fixture_source.mp4")
    clips = [os.path.join(out_dir, f"custom_{i}.mp4") for i in range(4)]
    if all(os.path.exists(p) and os.path.getsize(p) > 0 for p in [source] + clips):
        return {"source": source, "clips": clips}
    make_template_video(source,
                        shots=[(4.0, (200, 40, 40)), (3.0, (40, 200, 40)),
                               (4.0, (40, 40, 200)), (3.0, (240, 160, 40)),
                               (4.0, (200, 40, 200)), (3.0, (40, 200, 200))],
                        duration=21.0,
                        flash_at=[8.7, 17.3])
    for i, col in enumerate([(220, 60, 60), (60, 60, 220), (220, 220, 60), (60, 220, 160)]):
        make_clip(clips[i], 8.0, color=col)
    return {"source": source, "clips": clips}


if __name__ == "__main__":
    make_template_video("tests/fixture_source.mp4",
                        shots=[(4.0, (200, 40, 40)), (3.0, (40, 200, 40)),
                               (4.0, (40, 40, 200)), (3.0, (240, 160, 40)),
                               (4.0, (200, 40, 200)), (3.0, (40, 200, 200))],
                        duration=21.0,
                        flash_at=[8.7, 17.3])
    for i, col in enumerate([(220, 60, 60), (60, 60, 220), (220, 220, 60), (60, 220, 160)]):
        make_clip(f"tests/custom_{i}.mp4", 8.0, color=col)
    print("fixtures generated")