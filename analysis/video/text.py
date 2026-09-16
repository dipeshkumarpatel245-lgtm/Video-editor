"""Optional OCR text-overlay extraction.

Enabled via VT_USE_OCR=1 on deployments that have PaddleOCR installed
(needs paddlepaddle). Falls back to no-op otherwise.
"""
from __future__ import annotations
import os


def detect_text(video: str) -> list[dict]:
    if os.getenv("VT_USE_OCR", "0") != "1":
        return []
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
        # sample a frame every ~1s
        import subprocess
        from ffutils import run
        frames = f"/tmp/vt_ocr_{video.split('/')[-1]}_%03d.jpg"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video,
             "-vf", "fps=1,scale=960:-2", frames, "-y"], check=False)
        results = []
        for i in range(1, 120):
            p = frames.replace("%03d", f"{i:03d}")
            if not os.path.exists(p):
                break
            res = ocr.ocr(p, cls=False)
            for line in res or []:
                if not line:
                    continue
                for box, (text, conf) in line:
                    if conf > 0.6:
                        results.append({"t": i - 1, "text": text, "confidence": round(float(conf), 3)})
            os.remove(p)
        return results
    except ImportError:
        return []