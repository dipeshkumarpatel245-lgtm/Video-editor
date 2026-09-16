"""Format registry: export an Edit to every supported editor format."""
from __future__ import annotations
from . import capcut, edl, fcpx7, fcpxml

# fcpxml  = FCPXML 1.9 (DaVinci Resolve / Final Cut Pro X)
# premiere= FCP7 XMEML v5 (Adobe Premiere Pro)
# edl     = CMX3600 (universal fallback / conform workflows)
FORMATS = {
    "fcpxml": {"ext": "fcpxml", "mime": "application/xml", "fn": lambda e, t: fcpxml.export_fcpxml(e, t)},
    "premiere": {"ext": "xml", "mime": "application/xml", "fn": lambda e, t: fcpx7.export_fcpxml_7(e, t)},
    "edl": {"ext": "edl", "mime": "text/plain", "fn": lambda e, t: edl.export_edl(e, t)},
}


def export(edit: dict, fmt: str, title: str = "Recreated") -> tuple[str, bytes, str]:
    """Return (filename, content_bytes, mimetype) for a single format."""
    spec = FORMATS.get(fmt)
    if spec is None:
        raise KeyError(f"unknown export format {fmt!r}; known={list(FORMATS)}")
    text = spec["fn"](edit, title)
    fname = f"{title}.{spec['ext']}"
    return fname, text.encode("utf-8"), spec["mime"]


def export_capcut(edit: dict, title: str = "Recreated") -> str:
    """Write a CapCut draft folder; returns its path."""
    return capcut.export_capcut(edit, title)


def export_capcut_package(edit: dict, title: str = "Recreated") -> str:
    """Write a self-contained CapCut draft + bundled media; returns package root."""
    return capcut.export_capcut_package(edit, title)