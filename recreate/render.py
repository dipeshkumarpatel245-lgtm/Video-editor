"""Render an Edit to an MP4 via ffmpeg filter graphs (xfade, eq, zoompan, tpad)."""
from __future__ import annotations

import os
import shlex

from config import RENDER_FPS, RENDER_WIDTH
from edit import lint
from ffutils import run


def _xfade_type(ttype: str) -> str:
    return {
        "dissolve": "fade",
        "crossfade": "fade",
        "cross": "fade",
        "smoothness": "fade",
        "fadeblack": "fadeblack",
        "dip": "fadeblack",
        "flash": "fadewhite",
    }.get(ttype, "fade")


def build_filtergraph(edit: dict, W: int, H: int, R: float) -> str:
    segs = sorted(edit["segments"], key=lambda s: s["start"])
    n = len(segs)
    if n == 0:
        raise ValueError("empty edit (no segments)")

    min_d = 2.0 / R

    def seg_filter(i: int, seg: dict) -> str:
        s0 = seg["src_start"]
        s1 = seg["src_end"]
        speed = max(0.1, seg.get("speed", 1.0))
        ftail = seg.get("_fit", {}).get("freeze_tail", 0.0) if "_fit" in seg else 0.0
        f = f"[{i}:v]trim=start={s0}:end={s1},setpts=PTS-STARTPTS,setpts=PTS/{speed:.6f}"
        f += f",scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:0:0,setpts=PTS-STARTPTS"

        zseq = (seg.get("transform") or {}).get("zoom_seq")
        if zseq and len(zseq) >= 2:
            dur = max(0.1, (seg["end"] - seg["start"]) / speed)
            z0 = zseq[0]["zoom"]
            z1 = zseq[-1]["zoom"]
            frames = max(2, int(dur * R))
            step = (z1 - z0) / max(1, frames - 1)
            f += f",zoompan=z='min({z0:.5f}+{step:.6f}*on,{max(z0, z1)+0.2:.5f})':d=1:s={W}x{H}:fps={R}"
        f += f",fps={R}"

        col = seg.get("color") or {}
        mat = col.get("matrix")
        if isinstance(mat, (list, tuple)) and len(mat) >= 9:
            rr, gg, bb = float(mat[0]), float(mat[4]), float(mat[8])
            if any(abs(x - 1.0) > 1e-3 for x in (rr, gg, bb)):
                f += f",colorchannelmixer=rr={rr:.4f}:gg={gg:.4f}:bb={bb:.4f}"
        sat = col.get("sat", 1.0)
        exp = col.get("exposure", 0)
        contrast = col.get("contrast", 1.0)
        if abs(sat - 1.0) > 1e-3 or exp != 0 or abs(contrast - 1.0) > 1e-3:
            f += f",eq=saturation={sat:.3f}:brightness={exp:.3f}:contrast={contrast:.3f}"
        temp = col.get("temp", 0)
        if abs(temp) > 1e-3:
            k = max(2500, min(10500, 6500 - float(temp) * 12000.0))
            f += f",colortemperature=temperature={k:.0f}"
        f += ",setsar=1"
        if ftail > 0:
            f += f",tpad=stop_mode=clone:stop_duration={ftail:.4f}"
        return f

    parts: list[str] = []
    cur = "v0"
    seg0 = segs[0]
    total = (seg0["end"] - seg0["start"]) + _freeze(seg0)
    for i in range(1, n):
        seg = segs[i]
        prev = segs[i - 1]
        len_i = (seg["end"] - seg["start"]) + _freeze(seg)
        ti = seg.get("transition_in") or prev.get("transition_out")
        ttype = (ti or {}).get("type", "cut")
        d = float((ti or {}).get("duration", 0.0)) if (ti and ttype not in ("cut", "none", None)) else 0.0
        if ttype in ("cut", "none", None):
            d = min_d
            xf = "fade"
        else:
            d = max(min_d, d)
            xf = _xfade_type(ttype)
        offset = max(0.0, total - d)
        parts.append(f"[{cur}][v{i}]xfade=transition={xf}:duration={d:.6f}:offset={offset:.6f}[vx{i}]")
        total = total - d + len_i
        cur = f"vx{i}"

    for i, seg in enumerate(segs):
        filt = seg_filter(i, seg)
        outl = f"[v{i}]"
        parts.append(f"{filt}{outl}")

    parts.append(f"[{cur}]format=yuv420p[vout]")
    return ";\n".join(parts) + ";\n"


def _freeze(seg: dict) -> float:
    if "_fit" in seg:
        return float(seg.get("_fit", {}).get("freeze_tail", 0.0))
    return 0.0


def render(edit: dict, out_path: str, width: int | None = None, height: int | None = None,
           fps: float | None = None, progress_hook=None) -> str:
    problems = lint(edit)
    if problems:
        raise ValueError("invalid edit: " + "; ".join(problems))
    meta = edit["meta"]
    W = width or int(meta.get("width", RENDER_WIDTH))
    H = height or int(meta.get("height", 720))
    R = fps or float(meta.get("fps", RENDER_FPS))
    H = max(2, int(H))
    W = max(2, int(W))

    fg = build_filtergraph(edit, W, H, R)

    encoder = os.getenv("VT_ENCODER", "libx264")
    if encoder == "libx264":
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", os.getenv("VT_CRF", "20")]
    elif encoder == "nvenc":
        venc = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", os.getenv("VT_CQ", "20")]
    else:
        venc = ["-c:v", encoder]

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats"]
    for seg in sorted(edit["segments"], key=lambda s: s["start"]):
        cmd += ["-i", seg["file"]]
    has_audio = bool(meta.get("source_audio"))
    if has_audio:
        cmd += ["-i", meta["source_audio"]]
    cmd += ["-filter_complex", fg]
    cmd += ["-map", "[vout]"]
    if has_audio:
        cmd += ["-map", f"{len(edit['segments'])}:a?"]
    cmd += venc + ["-pix_fmt", "yuv420p"]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-r", str(int(round(R))), "-shortest", "-y", out_path]

    run(cmd, timeout=int(os.getenv("VT_RENDER_TIMEOUT", "3600")))
    return out_path


def build_preview_command(edit: dict, out_path: str, width=640, height=360, fps=15) -> list[str]:
    """Lower-res quick render used for timeline previews."""
    return ["ffmpeg", "-hide_banner", "-loglevel", "error",
            "-filter_complex", build_filtergraph(edit, width, height, fps),
            "-map", "[vout]", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "26", "-y", out_path]
