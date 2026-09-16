import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WORKSPACE = Path(os.getenv("VT_WORKSPACE", ROOT / "workspace"))

MEDIA_DIR = WORKSPACE / "media"
FRAMES_DIR = WORKSPACE / "frames"
ANALYSIS_DIR = WORKSPACE / "analysis"
TEMPLATE_DIR = WORKSPACE / "templates"
LUT_DIR = WORKSPACE / "luts"
EXPORT_DIR = WORKSPACE / "exports"
RENDER_DIR = WORKSPACE / "renders"
EDIT_DIR = WORKSPACE / "edits"

for d in (MEDIA_DIR, FRAMES_DIR, ANALYSIS_DIR, TEMPLATE_DIR, LUT_DIR, EXPORT_DIR, RENDER_DIR, EDIT_DIR):
    d.mkdir(parents=True, exist_ok=True)

FFMPEG = os.getenv("VT_FFMPEG", "ffmpeg")
FFPROBE = os.getenv("VT_FFPROBE", "ffprobe")

# Analysis defaults
ANALYSIS_FPS = float(os.getenv("VT_ANALYSIS_FPS", "15"))     # frames used for shot/motion analysis
ANALYSIS_WIDTH = int(os.getenv("VT_ANALYSIS_WIDTH", "192"))  # small proxy resolution
SAMPLE_RATE = int(os.getenv("VT_SAMPLE_RATE", "22050"))      # audio working rate (Hz)
CUT_THRESHOLD = float(os.getenv("VT_CUT_THRESHOLD", "7.0"))  # scene-diff z-score to call a cut
MIN_SHOT_SEC = float(os.getenv("VT_MIN_SHOT_SEC", "0.5"))
FLASH_LUMA = float(os.getenv("VT_FLASH_LUMA", "0.97"))       # mean frame luma to call a flash
TEMPO_LOW = int(os.getenv("VT_TEMPO_LOW", "50"))
TEMPO_HIGH = int(os.getenv("VT_TEMPO_HIGH", "200"))

# Render
RENDER_WIDTH = int(os.getenv("VT_RENDER_WIDTH", "1280"))
RENDER_FPS = int(os.getenv("VT_RENDER_FPS", "30"))
EXPORT_LUT_SIZE = int(os.getenv("VT_EXPORT_LUT_SIZE", "17"))

# Optional heavy backends (GPU workers can enable)
USE_OPENCV = os.getenv("VT_USE_OPENCV", "0") == "1"
USE_OCR = os.getenv("VT_USE_OCR", "0") == "1"

BROKER_URL = os.getenv("VT_BROKER_URL", "redis://localhost:6379/0")


def new_id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"