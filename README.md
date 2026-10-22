# Video Editor

A Python-based video editing and template recreation platform that analyzes source footage, extracts scene and motion structure, matches clips to template shots, and exports recreated edits for downstream editors.

This project combines:
- a FastAPI backend for uploads, analysis, recreation, rendering, and export
- a Python analysis pipeline for detection and feature extraction
- clip matching and edit generation logic for template-based recreations
- a lightweight web frontend served from the `web/` directory

## Features

- Upload template and clip videos
- Analyze video structure and scenes
- Extract motion, color, and audio cues
- Match clip content to template slots
- Recreate edits using replace or recut modes
- Export to FCPXML, Premiere-style formats, EDL, and CapCut package output
- Render preview MP4s for review
- Serve a SPA from the same web app

## Project Structure

```text
.
├── analysis/              # Video analysis and probing logic
│   ├── audio/
│   ├── video/
│   ├── fusion.py
│   ├── pipeline.py
│   └── probe.py
├── config.py              # Global config and directory setup
├── deploy/                # Deployment-related assets
├── edit.py                # Shared edit model definitions
├── export/                # Exporters and packaging logic
├── ffutils.py             # FFmpeg / FFprobe wrappers
├── recreate/              # Match, replace, recut, and render logic
│   ├── matching.py
│   ├── recut.py
│   ├── recommend.py
│   ├── render.py
│   └── replace.py
├── server/                # API and app bootstrap
│   ├── api.py
│   └── main.py
├── template/              # Template schema and storage
├── tests/                 # Test suite
├── web/                   # Frontend static assets
├── workers/               # Worker-related code
├── workspace/             # Runtime-generated media / generated outputs
├── .gitignore
├── pytest.ini
├── requirements.txt
├── README.md
└── ...
```

## Tech Stack

- Python 3
- FastAPI
- NumPy / SciPy
- OpenCV
- FFmpeg / FFprobe
- Celery + Redis
- Pillow
- Scenedetect
- Librosa

## Prerequisites

- Python 3.10+
- FFmpeg installed and available on PATH
- FFprobe installed and available on PATH
- Redis (for Celery/background job support if enabled)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/dipeshkumarpatel245-lgtm/Video-editor.git
cd Video-editor
```

2. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The project reads important runtime settings from environment variables through `config.py`.

Common settings include:

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

If you do not set these, sensible defaults are used.

## Running the App

Start the API server:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

- API docs: `http://localhost:8000/docs`
- Web app: `http://localhost:8000/`

## Main API Endpoints

The app exposes a REST API under `/api`.

- `POST /api/upload` — upload a template or clip video
- `POST /api/analyze` — analyze a template video and build a canonical template
- `GET /api/templates` — list saved templates
- `GET /api/templates/{template_id}` — fetch a specific template
- `POST /api/recreate` — generate a recreated edit
- `GET /api/edits/{edit_id}` — fetch edit JSON
- `POST /api/export` — export to a supported format
- `POST /api/render` — render a preview MP4
- `GET /api/render/stream/{name}` — stream a rendered video
- `GET /health` — health check

## Typical Workflow

1. Upload a template video.
2. Analyze it to create a template structure.
3. Upload one or more source clips.
4. Recreate the edit using template matching.
5. Export or render the final result.

## Notes

- Generated media and working files are created under the workspace directory configured by `VT_WORKSPACE`.
- The project is designed for video analysis and shot-level matching, so performance depends on media size, clip count, and CPU/GPU resources.
- Some features are optional and can be enabled via environment flags.

## Contributing

Contributions are welcome. For a smooth contribution flow:

1. Fork the project.
2. Create a feature branch.
3. Make the change.
4. Run the targeted test suite.
5. Create a pull request with a clear summary.

## License

This project does not currently declare a license in the repository metadata. Please check the repository settings or project ownership before commercial or public reuse.

## Important

This repository contains video-processing and media-analysis code. Ensure your environment has adequate CPU, RAM, and FFmpeg support before processing large files.

---

If you want, I can also generate:
- a shorter, more polished GitHub-style README
- a project-specific README tailored to this exact codebase with diagrams and screenshots
- a README in a more marketing / product style for public launch
