"""Detect scene cuts, dissolves, and flashes via frame-difference analysis (pure-numpy)."""
from __future__ import annotations
import numpy as np
from config import ANALYSIS_FPS, ANALYSIS_WIDTH, CUT_THRESHOLD, MIN_SHOT_SEC, FLASH_LUMA
from ffutils import run_ffmpeg


def _read_frames_raw(video: str, fps: float = ANALYSIS_FPS, width: int = ANALYSIS_WIDTH) -> tuple[np.ndarray, float, int]:
    """Read all frames as (N,H,W,3) uint8; returns (frames, real_fps, total_frames)."""
    import subprocess, shlex
    scale = f"scale={width}:-2"
    cmd = (
        f'ffmpeg -hide_banner -loglevel error -i {shlex.quote(video)} '
        f'-vf "{scale},fps={fps}" -pix_fmt rgb24 -f rawvideo -'
    )
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = proc.stdout.read()
    proc.wait()
    proc.stderr.close()
    proc.stdout.close()
    # probe actual fps
    probe_cmd = (
        f'ffprobe -v error -select_streams v:0 '
        f'-show_entries stream=r_frame_rate,duration,nb_frames '
        f'-of default=noprint_wrappers=1:nokey=1 {shlex.quote(video)}'
    )
    import subprocess as sp2
    fps_line = sp2.run(probe_cmd, shell=True, capture_output=True, text=True).stdout.strip()
    if "/" in fps_line:
        a, b = fps_line.split("/", 1)
        try:
            real_fps = float(a) / float(b)
        except:
            real_fps = fps
    else:
        try:
            real_fps = float(fps_line)
        except:
            real_fps = fps

    pixel_count = width * max(1, width * 9 // 16) * 3  # approx from width
    # figure out H: for 16:9, H = width*9/16 // 2 * 2
    H = max(2, (width * 9 // 16 // 2) * 2)
    W = width
    frame_bytes = W * H * 3
    n_frames = len(raw) // frame_bytes
    if n_frames == 0:
        return np.zeros((0, H, W, 3), dtype=np.uint8), real_fps, 0
    frames = np.frombuffer(raw[:n_frames * frame_bytes], dtype=np.uint8).reshape(n_frames, H, W, 3)
    return frames, real_fps, n_frames


def _luminance(frames: np.ndarray) -> np.ndarray:
    """Mean luma per frame (BT.709)."""
    return (0.2126 * frames[..., 0] + 0.7152 * frames[..., 1] + 0.0722 * frames[..., 2]).mean(axis=(-2, -1)) / 255.0


def _hist_diff(frames: np.ndarray, bins: int = 16) -> np.ndarray:
    """Per-frame 3D color-histogram difference (YUV quantised)."""
    if len(frames) < 2:
        return np.zeros(len(frames))
    from scipy.stats import pearsonr
    diffs = np.zeros(len(frames))
    prev_hist = None
    for i in range(len(frames)):
        f = frames[i].astype(np.float32)
        r, g, b = f[..., 0] / 255, f[..., 1] / 255, f[..., 2] / 255
        y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        u = (b - y) * 0.492
        v = (r - y) * 0.877
        hist, _ = np.histogramdd(
            np.stack([y.ravel(), u.ravel(), v.ravel()], -1),
            bins=bins, range=[(0, 1), (-0.5, 0.5), (-0.5, 0.5)],
        )
        hist = hist.astype(np.float64).ravel()
        hist /= hist.sum() + 1e-8
        if prev_hist is not None:
            diffs[i] = np.sum(np.abs(hist - prev_hist))
        prev_hist = hist
    return diffs


def _inter_frame_diff(frames: np.ndarray) -> np.ndarray:
    """Mean absolute per-pixel frame difference (luma channel)."""
    if len(frames) < 2:
        return np.zeros(len(frames))
    luma = _luminance(frames) * 255
    diff = np.abs(np.diff(luma))
    return np.concatenate([[0], diff])


def _scenedetect_cuts(video: str) -> np.ndarray:
    """Cut times (seconds) from PySceneDetect ContentDetector (frame-accurate)."""
    from scenedetect import open_video, SceneManager, ContentDetector
    video_obj = open_video(video)
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=27))
    sm.detect_scenes(video_obj)
    scenes = sm.get_scene_list()
    bounds = sorted({float(s[0].seconds) for s in scenes})
    return np.array([b for b in bounds if b > 1e-6])


def _legacy_cut_t(luma: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Legacy MAD-z-score luma-jump cut detection (fallback when scenedetect fails)."""
    D = np.abs(np.diff(luma)) * 255.0
    Dp = np.concatenate([[0.0], D])
    glob_med = float(np.median(Dp)) + 1e-6
    window = max(5, int(0.2 * ANALYSIS_FPS))
    z = np.zeros(len(luma))
    for i in range(len(luma)):
        lo, hi = max(0, i - window), min(len(luma), i + window + 1)
        seg = np.concatenate([Dp[lo:max(lo, i - 2)], Dp[min(len(luma), i + 3):hi]])
        if len(seg) == 0:
            continue
        m = float(np.median(seg))
        mad_ = float(np.median(np.abs(seg - m))) + 1e-6
        z[i] = (Dp[i] - m) / max(mad_, 0.25 * m)
    has_cut = (Dp > max(glob_med * 15.0, 8.0)) & (z > CUT_THRESHOLD)
    has_cut = has_cut | (Dp > glob_med * 40.0)
    ci = np.where(has_cut)[0]
    return times[ci] if len(ci) else np.array([])


def detect_shots(video: str) -> dict:
    """
    Returns dict with:
      shots:     [{start, end, idx}]
      cuts:      [{t, frame_idx}]
      dissolves: [{t_start, t_end, confidence}]
      flashes:   [{t}]
      metadata:  {analysis_fps, real_fps, n_frames}
    """
    frames, real_fps, n_frames = _read_frames_raw(video)
    if n_frames < 3:
        total_dur = n_frames / max(1, real_fps) if real_fps else 0
        return {
            "shots": [{"start": 0.0, "end": total_dur, "idx": 0}],
            "cuts": [], "dissolves": [], "flashes": [],
            "metadata": {"analysis_fps": ANALYSIS_FPS, "real_fps": real_fps, "n_frames": n_frames},
        }

    hist_d = _hist_diff(frames)
    luma = _luminance(frames)

    times = np.arange(n_frames) / ANALYSIS_FPS
    duration = (n_frames - 1) / ANALYSIS_FPS

    # ---- cut detection: PySceneDetect ContentDetector, legacy MAD-z fallback ----
    try:
        cut_t = _scenedetect_cuts(video)
    except Exception:
        cut_t = _legacy_cut_t(luma, times)
    if len(cut_t):
        merged = [cut_t[0]]
        min_gap = MIN_SHOT_SEC * 0.5
        for t in cut_t[1:]:
            if t - merged[-1] > min_gap:
                merged.append(t)
        cut_t = np.array(merged)
    cuts = [{"t": round(float(t), 4), "frame_idx": int(round(t * ANALYSIS_FPS))}
             for t in cut_t]

    # ---- flash detection: isolated brightness *spike* above neighbours ----
    import scipy.ndimage as ndi
    med_luma = ndi.median_filter(luma, size=int(0.15 * ANALYSIS_FPS) | 1)
    flash_mask = (luma > FLASH_LUMA) & ((luma - med_luma) > 0.12)
    flash_indices = np.where(flash_mask)[0]
    if len(flash_indices):
        merged_f = [flash_indices[0]]
        min_gap_f = int(0.1 * ANALYSIS_FPS)
        for j in flash_indices[1:]:
            if j - merged_f[-1] > min_gap_f:
                merged_f.append(j)
        flashes = [{"t": round(float(times[j]), 4)} for j in merged_f]
    else:
        flashes = []

    # drop cuts that are actually flash frames (a white flush is a transition, not a new shot)
    if len(cuts) and flashes:
        flash_t = [f["t"] for f in flashes]
        keep = []
        for c in cuts:
            if not any(abs(c["t"] - ft) <= (0.8 / ANALYSIS_FPS) for ft in flash_t):
                keep.append(c)
        cuts = keep
        cut_t = np.array([c["t"] for c in cuts])

    # ---- dissolve detection (sustained moderate diff between two cuts) ----
    cut_indices = np.minimum(((cut_t * ANALYSIS_FPS).astype(int)), n_frames - 1)
    all_bound = np.concatenate([[0], cut_indices, [n_frames - 1]])
    dissolves = []
    for i in range(len(all_bound) - 1):
        s, e = all_bound[i], all_bound[i + 1]
        seg = hist_d[s:e]
        if len(seg) < int(0.4 * ANALYSIS_FPS):
            continue
        if (e - s) / ANALYSIS_FPS > 2.0:  # dissolves are short; longer = pacing region
            continue
        mean_d = seg.mean()
        if 0.02 < mean_d < 0.10:  # moderate, not a hard cut
            std_d = seg.std()
            if std_d < mean_d * 1.5:  # sustained (low variance)
                dissolves.append({
                    "t_start": round(float(times[s]), 4),
                    "t_end": round(float(times[e]), 4),
                    "confidence": round(float(1.0 - std_d / (mean_d + 1e-6)), 3),
                })

    # ---- build shots ----
    boundary_times = [0.0] + [float(b) for b in cut_t] + [float(duration)]
    boundary_times = sorted(set(boundary_times))
    # drop boundaries too close to the previous kept boundary (tiny shots)
    kept = [0.0]
    for b in boundary_times[1:]:
        if b == float(duration):
            continue
        if b - kept[-1] >= MIN_SHOT_SEC * 0.8:
            kept.append(b)
    if kept[-1] < float(duration) - 1e-6:
        kept.append(float(duration))
    boundary_times = kept
    shots = []
    for idx in range(len(boundary_times) - 1):
        shots.append({
            "start": round(float(boundary_times[idx]), 4),
            "end": round(float(boundary_times[idx + 1]), 4),
            "idx": idx,
        })

    return {
        "shots": shots,
        "cuts": cuts,
        "dissolves": dissolves,
        "flashes": flashes,
        "metadata": {
            "analysis_fps": ANALYSIS_FPS,
            "real_fps": real_fps,
            "n_frames": n_frames,
        },
    }