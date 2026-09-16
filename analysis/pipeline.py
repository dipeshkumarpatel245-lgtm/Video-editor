from . import probe
from .audio import beats, extract, loudness, sound_events
from .video import color, content, motion, shots, speed, text
from .fusion import fuse


def analyze(video_path: str, cache_dir: str | None = None,
            progress: callable = None) -> dict:
    """Run the full analysis pipeline; returns canonical template dict."""
    def _prog(p: float, msg: str):
        if progress:
            progress(p, msg)

    _prog(0.02, "probing")
    info = probe.probe(video_path)

    _prog(0.08, "extracting audio")
    wav = extract.extract_audio(video_path)

    _prog(0.15, "beats & tempo")
    beat = beats.detect_beats(wav)

    _prog(0.22, "loudness")
    loud = loudness.analyze_loudness(wav)

    _prog(0.28, "sound events")
    events = sound_events.detect_sound_events(wav)

    _prog(0.35, "shot detection")
    shots_res = shots.detect_shots(video_path)

    _prog(0.55, "camera motion")
    motion_res = motion.analyze_motion(video_path)

    _prog(0.70, "speed/pacing")
    speed_res = speed.detect_speed(video_path)

    _prog(0.80, "color grade")
    frames, fps, _n = shots._read_frames_raw(video_path)
    color_res = color.analyze_color(frames, shots_res["shots"], fps)

    _prog(0.90, "content features")
    content_res = []
    for sh in shots_res["shots"]:
        content_res.append(content.shot_feature(frames, sh, fps))
    cidx = 0
    for sh in shots_res["shots"]:
        sh["content"] = content_res[cidx]
        cidx += 1

    _prog(0.95, "ocr (optional)")
    ocr_res = text.detect_text(video_path)

    _prog(0.98, "fusing")
    template = fuse(
        probe=info, beats=beat, loudness=loud, shots=shots_res,
        motion=motion_res, speed=speed_res, color=color_res, text=ocr_res,
        sound_events=events,
    )
    return template