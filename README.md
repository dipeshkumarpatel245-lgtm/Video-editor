# Video Template Studio

A Python-based video editing workflow for analyzing template footage, extracting shot structure and motion cues, matching source clips to template segments, and generating recreated edits for export or preview rendering.

This project combines:
- a FastAPI backend for uploads, analysis, matching, export, and rendering
- a Python media-analysis pipeline for video, audio, and scene extraction
- template-driven edit generation logic for replace/recut workflows
- a lightweight frontend served from the `web/` directory

## What the project does

The app is organized around a template-based editing flow:

1. Upload a template video
2. Analyze its scene structure and timing
3. Upload one or more source clips
4. Match those clips to template slots using visual/audio similarity
5. Recreate the edit in either replace or recut mode
6. Export or render the final result

This is not a general-purpose offline editor; it is designed around shot-level matching and template reconstruction.

## Features

- Upload template and clip videos
- Analyze video structure and scene timing
- Extract motion, color, and audio features
- Match clips to template shot slots
- Recreate edits using replace or recut behavior
- Export to FCPXML, Premiere-style output, EDL, and CapCut package formats
- Render preview MP4s for review
- Serve a lightweight SPA from the same application

## Repository structure

```text
.
├── analysis/              # Video and audio analysis code
│   ├── audio/
│   ├── video/
│   ├── fusion.py
│   ├── pipeline.py
│   └── probe.py
├── config.py              # Global app config and environment defaults
├── deploy/                # Deployment-related assets
├── edit.py                # Shared edit model definitions
├── export/                # Exporters and packaging logic
├── ffutils.py             # FFmpeg / FFprobe wrappers
├── recreate/              # Matching, recommendation, rendering, replace/recut logic
│   ├── matching.py
│   ├── recut.py
│   ├── recommend.py
│   ├── render.py
│   └── replace.py
├── server/                # FastAPI app bootstrap and API routes
│   ├── api.py
│   └── main.py
├── template/              # Template schema and stored template definitions
├── tests/                 # Test suite
├── web/                   # Frontend static assets
├── workers/               # Worker-related code
├── workspace/             # Generated media and outputs
├── .gitignore
├── pytest.ini
├── requirements.txt
├── README.md
└── ...
```

## Tech stack

- Python 3
- FastAPI
- NumPy / SciPy
- OpenCV
- FFmpeg / FFprobe
- Celery + Redis
- Pillow
- Scenedetect
- Librosa

## Requirements

- Python 3.10+
- FFmpeg installed and available on `PATH`
- FFprobe installed and available on `PATH`
- Redis if Celery/background worker support is enabled

## Installation

Clone the repository:

```bash
git clone https://github.com/dipeshkumarpatel245-lgtm/Video-editor.git
cd Video-editor
```

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The app reads runtime settings via `config.py` using environment variables.

Common options:

```bash
export VT_WORKSPACE=/path/to/workspace
export VT_FFMPEG=ffmpeg
export VT_FFPROBE=ffprobe
export VT_ANALYSIS_FPS=15
export VT_RENDER_WIDTH=1280
export VT_RENDER_FPS=30
export VT_USE_OPENCV=0
export VT_USE_OCR=0
export VT_BROKER_URL=redis://localhost:6379/0
```

If these are not set, the project falls back to sensible defaults.

## Running the app

Start the API server:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Then browse:

- API documentation: `http://localhost:8000/docs`
- Web app: `http://localhost:8000/`

## API overview

The app exposes its REST API under `/api`.

Key endpoints include:

- `POST /api/upload` — upload a template or clip video
- `POST /api/analyze` — analyze a template video and create a canonical template
- `GET /api/templates` — list saved templates
- `GET /api/templates/{template_id}` — fetch a specific template
- `POST /api/recreate` — generate a recreated edit
- `GET /api/edits/{edit_id}` — fetch an edit payload
- `POST /api/export` — export to a supported format
- `POST /api/render` — render a preview MP4
- `GET /api/render/stream/{name}` — stream a rendered video
- `GET /health` — health status

## Typical workflow

1. Upload a template video
2. Analyze it to extract scene and timing structure
3. Upload one or more source clips
4. Recreate the edit using match-and-fill logic
5. Export or render the final result

## Implementation notes

The codebase is organized around a few main responsibilities:

- `analysis/` handles frame sampling, shot detection, and content extraction
- `template/` stores and validates analyzed template structure
- `recreate/` performs clip assignment, matching, and edit assembly
- `export/` produces downstream editing packages and formats
- `server/` exposes the FastAPI API and serves the frontend

Generated media and working files are stored under the configured workspace directory (default: `workspace/`).

## License

This repository does not currently declare a license in the project metadata. If you intend to reuse, publish, or commercialize the code, check repository ownership and licensing status before doing so.

## Important

This project processes large media files and performs computational analysis on video content. Depending on file size and clip count, it may require significant CPU, RAM, and FFmpeg support.

---

This project is best understood as a template-driven video recreation engine rather than a general-purpose editing suite.
