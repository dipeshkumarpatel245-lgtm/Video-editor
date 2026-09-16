"""CapCut / Jianying desktop draft export (best-effort minimal draft generator).

Produces a `draft_content.json` + sidecar files that CapCut desktop can open:
copy the output folder into your CapCut "Drafts" directory. Full-fidelity effects
(auto/colour/LUT keyframes) are out of scope for this generator; cut/edit/transition/
text/audio structure is preserved. FCPXML/EDL remain the "any editor" aisle.
"""
from __future__ import annotations
import json, os, shutil, time, uuid
from pathlib import Path
from config import EXPORT_DIR


def _us(sec: float) -> int:
    return int(round(sec * 1_000_000))


def export_capcut(edit: dict, title: str = "VT_draft") -> str:
    meta = edit["meta"]
    fps = float(meta.get("fps", 30))
    width = int(meta.get("width", 1920))
    height = int(meta.get("height", 1080))
    duration_us = _us(meta.get("duration", 0.0))
    segments = sorted(edit["segments"], key=lambda s: s["start"])

    draft_id = f"D{int(time.time() * 1000)}"
    videos: list[dict] = []
    transitions: list[dict] = []
    texts_attach: list[dict] = []
    text_materials: list[dict] = []
    video_segments: list[dict] = []

    used_paths = {}
    for i, seg in enumerate(segments):
        path = str(Path(seg["file"]).resolve())
        mat_id = f"VIDEO_{i}"
        if path not in used_paths:
            mat = {
                "id": mat_id,
                "type": "video",
                "path": path,
                "duration": _us(max(seg["src_end"] - seg["src_start"], seg["end"] - seg["start"])),
                "width": width,
                "height": height,
                "rotate": 0,
                "mtime": int(os.path.getmtime(seg["file"]) * 1000) if os.path.exists(seg["file"]) else 0,
                "is_original_size": False,
                "is_precision_material": False,
                "is_lock": False,
                "is_color_placement_on": False,
                "is_rgb_curves_on": False,
                "video_algorithm_type": "0",
                "config_path": "0",
                "audio_algorithm_type": "0",
                "audio_mute": False,
                "fps": fps,
                "can_lock": True,
                "can_reverse": True,
                "can_delete": True,
                "prefer_face_mask": False,
                "crop": [],
                "desc": "",
                "format_initial": False,
                "format_from_to": [],
                "vcid": "",
                "audio_delay": 0.0,
                "audio_volume": 100,
                "audio_scale": 1.0,
                "request_view_reverse": False,
                "request_repeat_fill": 0,
                "request_duplicate_fill": 0,
                "import_privacy_grade_id": "",
                "export_privacy_grade_id": "",
                "tags": [],
                "required_effect_type": "",
                "captions_url": "",
            }
            videos.append(mat)
            used_paths[path] = mat_id

        seg_id = f"SEG_{i}"
        tr_start = _us(seg["start"])
        seg_dur = _us(max(0.0, seg["end"] - seg["start"]))
        src_start = _us(seg["src_start"])
        src_dur = _us(max(0.0, seg["src_end"] - seg["src_start"]))

        ts = {}
        ti = seg.get("transition_in")
        ttype = (ti or {}).get("type", "cut")
        if ttype not in ("cut", "none", None):
            t_dur_ms = int(float(ti.get("duration", 0.5)) * 1000)
            extra = _cc_transition(ttype)
            tid = f"TR_{i}"
            transitions.append({
                "id": tid,
                "name": extra,
                "type": "transition",
                "platform": "all",
                "duration": t_dur_ms,
                "extra_type": extra,
                "extra_type_options": {},
                "redirect": False,
                "is_face_point_transition": False,
                "may_need_repeat_tips": 0,
            })
            ts = {
                "transition": {
                    "id": tid,
                    "duration": t_dur_ms,
                    "type": "transition",
                    "name": extra,
                }
            }

        seg_dict = {
            "id": seg_id,
            "target_timerange": {"duration": seg_dur, "start": tr_start},
            "source_timerange": {"duration": src_dur, "start": src_start},
            "render_index": 0,
            "speed": seg.get("speed", 1.0),
            "extra_type_option": 0,
            "clip": {
                "id": used_paths[path],
                "type": "video",
                "speed_curve_ref": False,
            },
            "transitions": ts,
            "volume": 100,
            "extra_type_options": {"version": 0, "opt_a": 0, "opt_b": 0, "opt_c": 0},
            "martian_extra_data": "",
            "keyframes": [],
            "audios": [],
            "image_filters": [],
            "text_attach": {},
            "cluster_name": "",
        }
        video_segments.append(seg_dict)

        # text overlays -> text track segments + materials
        for t in seg.get("text", []):
            tmat_id = f"TEXT_{i}_{len(text_materials)}"
            tseg_id = f"TSEG_{i}_{len(text_materials)}"
            text_materials.append({
                "id": tmat_id,
                "type": "text",
                "format": {
                    "bold": 0, "italic": 0, "underline": 0, "font_id": "0",
                    "color": "#FFFFFF", "font_size": 120, "alignment": 2,
                },
                "content": t.get("text", ""),
                "layer_name": "TEXT",
            })
            texts_attach.append({
                "id": tseg_id,
                "target_timerange": {
                    "duration": _us(t.get("end", 1.0) - t.get("start", 0.0)),
                    "start": _us(seg["start"] + t.get("start", 0.0)),
                },
                "render_index": 0,
                "clip": {"id": tmat_id, "type": "text", "speed_curve_ref": False},
                "extra_type_options": {"version": 0, "opt_a": 0, "opt_b": 0, "opt_c": 0},
                "keyframes": [],
            })

    vtr_id = f"TRACKV_{int(time.time()*1000)}"
    ttr_id = f"TRACKT_{int(time.time()*1000)}"
    tracks = [
        {
            "id": vtr_id,
            "type": "video",
            "flag": 0,
            "segments": video_segments,
            "is_default_visible": True,
            "attribute": 0,
            "segment_speed": [],
        },
        {
            "id": ttr_id,
            "type": "text",
            "flag": 0,
            "segments": texts_attach,
            "is_default_visible": True,
            "attribute": 0,
            "segment_speed": [],
        },
    ]

    now = int(time.time())
    draft = {
        "id": draft_id,
        "name": title,
        "duration": duration_us,
        "fps": fps,
        "canvas_config": {"width": width, "height": height, "ratio": "16:9"},
        "platform": {"app_source": "cc", "app_version": "6.5.0", "os": "mac", "channel": "demo"},
        "materials": {
            "videos": videos,
            "audios": [],
            "texts": text_materials,
            "stickers": [],
            "video_effects": [],
            "transitions": transitions,
            "masks": [],
            "chromas": [],
            "audio_fades": [],
            "audio_effects": [],
            "canvases": [],
            "speeds": [],
            "sound_channel_mappings": [],
            "vocal_separations": [],
            "placeholders": [],
            "common_mask": [],
            "posters": [],
        },
        "tracks": tracks,
        "timeline_tracks": {
            "single_layer_tracks": tracks,
            "assemble_tracks": [],
        },
        "extra_info": {"created_via": "videotemplate"},
        "video_algorithm_config": {},
        "render_hdr_settings": {"aces_llr_mapping": 1, "aces_mlr_mapping": 1, "prefer_aces": 0},
        "new_version": "30000000",
        "cover": "bmU6Ly8vcGxhY2Vob2xkZXI=",
        "create_time": now,
        "update_time": now,
        "is_ai_draft": False,
        "is_lock": False,
        "is_non_usable": False,
        "is_pending_render": False,
        "is_playable": True,
        "is_project_modified": False,
        "is_save_entire_layout": True,
        "deleted_track_ids": [],
        "export_resolution": 1080,
        "export_frame_rate": int(round(fps)),
        "tmpl_info": {},
        "paint_data": {},
        "is_legacy_draft": False,
        "anti_flicker_status": -1,

        "first_eofd": 0,
        "first_eofc": 0,
        "first_eoft": 0,
        "first_e_of_small_auxiliary_effect_t": 0,
        "first_e_of_small_auxiliary_effect_c": 0,
        "first_e_of_small_auxiliary_effect_d": 0,
        "segments": [],
        "tracks_details": {},
        "draft_edit_tab_pref": {},
        "timeline_tracks_ptr": "/timeline_tracks",
    }

    out_dir = EXPORT_DIR / f"{title}_cc"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "draft_content.json").write_text(json.dumps(draft, ensure_ascii=False))
    info = {
        "authors": [],
        "create_type": "empty",
        "creation_time": now,
        "duration": duration_us,
        "export_resolution": "1080",
        "fps": fps,
        "id": draft_id,
        "indicator": {},
        "latest_ipc_time": 0,
        "latest_updated_time": 0,
        "random_id": uuid.uuid4().hex,
        "update_time": now,
        "used_video_algorithm": "",
        "uses_hdr": 0,
        "uses_rtc": 0,
    }
    (out_dir / "draft_info.json").write_text(json.dumps(info))
    (out_dir / "draft_meta_info.json").write_text(json.dumps({
        "draft_meta_info": {"is_default": True, "is_playable": True},
    }))
    return str(out_dir)


def export_capcut_package(edit: dict, title: str = "VT_pkg") -> str:
    """Self-contained CapCut bundle: draft + media copied next to it with the
    material `path` fields rewritten to `../media/<name>` so the project imports
    on another machine. Returns the package root dir (contains <title>_cc/ + media/)."""
    draft_dir = Path(export_capcut(edit, title))
    pkg_root = EXPORT_DIR / f"{title}_cc_pkg"
    if pkg_root.exists():
        shutil.rmtree(pkg_root)
    media_dir = pkg_root / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    draft = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
    copied: set[str] = set()

    def _rewrite(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "path" and isinstance(v, str) and v.startswith("/"):
                    name = os.path.basename(v)
                    if os.path.exists(v) and name not in copied:
                        shutil.copy2(v, media_dir / name)
                        copied.add(name)
                    o[k] = os.path.join("..", "media", name)
                else:
                    _rewrite(v)
        elif isinstance(o, list):
            for i in o:
                _rewrite(i)

    _rewrite(draft)
    dest = pkg_root / draft_dir.name
    shutil.copytree(draft_dir, dest)
    (dest / "draft_content.json").write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    return str(pkg_root)


def _cc_transition(ttype: str) -> str:
    return {
        "dissolve": "smoothness",
        "crossfade": "smoothness",
        "cross": "smoothness",
        "fadeblack": "fade_black",
        "dip": "fade_black",
        "flash": "dodge_filter",
        "push": "cross_zoom",
        "cross_zoom": "cross_zoom",
    }.get(ttype, "smoothness")