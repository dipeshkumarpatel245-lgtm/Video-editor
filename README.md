# Video Template Studio

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/OpenCV-Enabled-5C3EE8" alt="OpenCV" />
  <img src="https://img.shields.io/badge/FFmpeg-Required-0078D4?logo=ffmpeg&logoColor=white" alt="FFmpeg" />
</p>

A Python-powered video editing workflow for analyzing reference footage, matching source clips to template segments, and recreating polished edits for export and rendering.

If you have a reference edit and want to rebuild it using different source footage, this project helps automate that process.

## Why this project exists

Most video editing workflows are manual, slow, and repetitive. This project is built for a specific problem:

- A team has a reference edit or template video
- They want to recreate the same structure using new or alternate clips
- They need matching, timing, and export automation instead of doing everything by hand

This repo helps automate that workflow with analysis, matching, and edit reconstruction.

## What it does

The app is organized around a template-driven video recreation flow:

1. Upload a template video
2. Analyze its scene structure, timing, and visual/audio cues
3. Upload one or more source clips
4. Match those clips to template slots using similarity analysis
5. Recreate the edit in replace or recut mode
6. Export or render the final result

This is not a general-purpose offline editor. It is designed around edit reconstruction from a reference workflow.

## Ideal use cases

- Rebuilding a reference edit with alternate source footage
- Matching clips to a template structure for content repurposing
- Creating standardized video variations from approved edit patterns
- Template-based content workflows for agencies, marketing teams, and creators

## Core features

- Template and clip upload workflow
- Video and audio scene analysis
- Shot timing and motion extraction
- Visual/audio feature matching
- Replace and recut reconstruction modes
- Export support for FCPXML, Premiere-style output, EDL, and CapCut package formats
- Render preview MP4 outputs
- FastAPI backend and lightweight web frontend

## Repository structure

```text
.
├── analysis/              # Video and audio analysis code
│   ├── audio/
│   ├── video/
│   ├── fusion.py
│   ├── pipeline.py
│   └── probe.py
├── config.py              # Runtime config and environment settings
├── deploy/                # Deployment assets
├── edit.py                # Shared edit model definitions
├── export/                # Exporters and packaging logic
├── ffutils.py             # FFmpeg / FFprobe wrappers
├── recreate/              # Matching, recommendation, rendering, and assembly logic
│   ├── matching.py
│   ├── recut.py
│   ├── recommend.py
│   ├── render.py
│   └── replace.py
├── server/                # FastAPI app and API routes
│   ├── api.py
│   └── main.py
├── template/              # Template schema and stored definitions
├── tests/                 # Automated tests
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

- Python 3.10+
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
- Redis if background worker support is enabled

## Quick start

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

The app reads runtime settings from `config.py` and environment variables.

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

## Run the app

Start the API server:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

- API docs: `http://localhost:8000/docs`
- Web app: `http://localhost:8000/`

## API overview

The app exposes its REST API under `/api`.

Key endpoints include:

- `POST /api/upload` — upload a template or source clip
- `POST /api/analyze` — analyze a template and create a canonical structure
- `GET /api/templates` — list saved templates
- `GET /api/templates/{template_id}` — fetch a template
- `POST /api/recreate` — generate a recreated edit
- `GET /api/edits/{edit_id}` — fetch edit data
- `POST /api/export` — export to a supported format
- `POST /api/render` — render a preview MP4
- `GET /api/render/stream/{name}` — stream a rendered video
- `GET /health` — health status

## Typical workflow

1. Upload a reference template video
2. Analyze it to extract scene timing and structure
3. Upload one or more source clips
4. Recreate the edit using match-and-fill logic
5. Export or render the final result

## Implementation notes

The codebase is organized around a few main responsibilities:

- `analysis/` handles frame sampling, shot detection, and content extraction
- `template/` stores and validates analyzed template structure
- `recreate/` performs clip matching, recommendation, and edit assembly
- `export/` produces downstream editing packages and formats
- `server/` exposes the FastAPI API and serves the frontend

Generated media and working files are stored under the workspace directory (default: `workspace/`).

## License

This repository does not currently declare a license in the project metadata. If you intend to reuse, publish, or commercialize the code, check repository ownership and licensing status before doing so.

## Important note

This project processes large media files and performs computational analysis on video content. Depending on file size and clip count, it may require significant CPU, RAM, and FFmpeg support.

---

Video Template Studio is a template-driven video recreation engine designed to help automate edit reconstruction from reference footage and matching source clips.
