"""Probe video metadata via ffprobe."""
from __future__ import annotations
from config import FFPROBE
from ffutils import probe_json


def probe(filepath: str) -> dict:
    data = probe_json(filepath)
    fmt = data.get("format", {})
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    aud = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})

    fps = eval_fractions(vs.get("r_frame_rate", "0/1"))  # type: ignore
    duration = float(fmt.get("duration", vs.get("duration", 0)))

    return {
        "duration": duration,
        "fps": fps or 30.0,
        "width": int(vs.get("width", 0)),
        "height": int(vs.get("height", 0)),
        "pixel_format": vs.get("pix_fmt"),
        "video_codec": vs.get("codec_name"),
        "video_bitrate": int(vs.get("bit_rate", 0) or 0),
        "audio_codec": aud.get("codec_name"),
        "audio_channels": int(aud.get("channels", 0) or 0),
        "audio_sample_rate": int(aud.get("sample_rate", "0") or 0),
        "audio_bitrate": int(aud.get("bit_rate", 0) or 0),
        "format_name": fmt.get("format_name", ""),
        "nb_streams": int(fmt.get("nb_streams", 0)),
    }


def eval_fractions(s: str) -> float:
    if "/" in s:
        a, b = s.split("/", 1)
        try:
            return float(a) / float(b)
        except ZeroDivisionError:
            return 0.0
    return float(s or 0)