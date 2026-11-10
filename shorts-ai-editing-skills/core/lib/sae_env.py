"""Detect what THIS machine can actually run and build a CapabilityManifest from it.

Used by scripts/shorts.py when no audited editor manifest is given (standalone / OpenCode use).
Every 'implemented' entry carries the evidence that was probed (FFmpeg filter list, imports).
"""
from __future__ import annotations

import datetime
import shutil
import subprocess
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[2]


def _out(cmd) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return (r.stdout or "") + (r.stderr or "")
    except Exception:  # noqa: BLE001
        return ""


def ffmpeg_facts() -> Dict:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return {"ok": False}
    ver = _out(["ffmpeg", "-hide_banner", "-version"])
    filters = _out(["ffmpeg", "-hide_banner", "-filters"])
    xf = _out(["ffmpeg", "-hide_banner", "-h", "filter=xfade"])
    has = lambda f: f" {f} " in filters  # noqa: E731
    return {"ok": True, "version": ver.splitlines()[0] if ver else "?", "has": has, "libass": "--enable-libass" in ver and has("subtitles"),
            "xfadeNames": all(f" {n} " in xf for n in ("fade", "smoothleft", "smoothup", "zoomin", "hblur"))}


def python_facts() -> Dict:
    facts = {"opencv": False, "haar": False, "fasterWhisper": False}
    try:
        import cv2  # noqa: F401
        facts["opencv"] = True
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import subject_boxes
        try:
            subject_boxes.haar_path()
            facts["haar"] = True
        except RuntimeError:
            pass
    except ImportError:
        pass
    try:
        import faster_whisper  # noqa: F401
        facts["fasterWhisper"] = True
    except ImportError:
        pass
    return facts


def build_manifest(width: int = 1080, height: int = 1920, fps: float = 30.0, word_timestamps: bool = True,
                   detect_faces: bool = False) -> Dict:
    f = ffmpeg_facts()
    p = python_facts()
    caps: Dict[str, Dict] = {}

    def put(key, ok, evidence, notes=""):
        caps[key] = {"status": "implemented" if ok else "missing", "evidence": evidence if ok else ""}
        if notes or not ok:
            caps[key]["notes"] = notes or "not available on this machine"

    ff = f["ok"]
    h = f.get("has", lambda _x: False)
    ev = f"probed {f.get('version', 'no ffmpeg')}"
    put("media.probe", ff, "ffprobe on PATH")
    put("transcript.phrase", True, "transcript file or local ASR")
    put("transcript.wordTimestamps", word_timestamps, "transcript.wordTimestampsReliable == true",
        "" if word_timestamps else "transcript has no reliable word timings -> phrase captions")
    put("analysis.silenceDetect", ff and h("silencedetect"), ev)
    put("analysis.sceneDetect", ff and h("select") and h("showinfo"), ev)
    put("analysis.subjectBoxes", detect_faces and p["opencv"] and p["haar"], "OpenCV Haar cascade",
        "" if (p["opencv"] and p["haar"]) else "pip install opencv-python-headless (4.x) and pass --detect-faces")
    put("analysis.loudnessMeasure", ff and h("loudnorm"), ev)
    put("analysis.beatDetect", False, "", "use user BPM or Skill 07 estimate_bpm offline")
    put("analysis.semanticLLM", False, "", "agent/LLM may supply intent only")
    put("analysis.visionLLM", False, "", "agent may view contact_sheet.png itself")
    put("timeline.cutList", ff and h("trim") and h("concat"), ev)
    put("timeline.reorder", False, "", "not supported in v1")
    put("overlay.text", ff and f.get("libass", False), "libass subtitles filter")
    put("overlay.alpha", ff and h("overlay"), ev)
    put("overlay.motionPresets", False, "", "ASS animations only; full presets need an overlay renderer")
    put("overlay.groups", False, "", "needs an overlay renderer")
    put("overlay.assSubtitles", ff and f.get("libass", False), "ffmpeg --enable-libass + subtitles filter")
    put("camera.transform", ff and h("scale") and h("crop"), ev)
    caps["camera.subpixel"] = {"status": "incompatible", "notes": "FFmpeg crop is integer-pixel"}
    put("transition.xfade", ff and h("xfade") and f.get("xfadeNames", False), ev)
    put("transition.custom", False, "", "")
    put("vfx.blur", ff and h("gblur"), ev)
    put("vfx.colorAdjust", ff and h("eq") and h("vignette"), ev)
    put("vfx.glow", ff and h("gblur") and h("blend"), ev)
    put("vfx.mask", False, "", "needs an overlay renderer")
    put("vfx.motionBlur", ff and h("tmix"), ev)
    put("audio.loudnorm", ff and h("loudnorm"), ev)
    put("audio.duck", ff and h("volume") and h("amix"), ev)
    put("audio.mixSfx", ff and h("amix") and h("adelay"), ev)
    put("audio.crossfade", ff and h("afade"), ev)
    put("audio.denoise", ff and h("afftdn"), ev)
    put("render.preview", ff, ev)
    put("render.export", ff, ev)
    put("render.frameExtract", ff, ev)
    return {"manifestVersion": "1.0", "auditedAt": datetime.date.today().isoformat(),
            "editor": {"name": "standalone shorts.py (auto-detected)", "repoRoot": str(ROOT), "renderEngine": "ffmpeg" if ff else "unknown",
                       "previewEngine": "same FFmpeg pipeline", "previewMatchesExport": True},
            "output": {"width": width, "height": height, "fps": fps}, "capabilities": caps,
            "_facts": {"ffmpeg": f.get("version"), **p}}
