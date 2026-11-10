"""Environment check for the user's machine (Windows/macOS/Linux). Writes doctor-report.json.

    python scripts/doctor.py
Send doctor-report.json back if something fails — it contains versions and capability probes,
no media and no personal files.
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core/lib"))


def sh(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    rep = {"python": sys.version.split()[0], "platform": platform.platform(), "checks": {}}
    ok = True

    def check(name, passed, detail="", required=True):
        nonlocal ok
        rep["checks"][name] = {"ok": bool(passed), "required": required, "detail": str(detail)[:400]}
        ok = ok and (passed or not required)
        print(f"{'OK  ' if passed else ('FAIL' if required else 'warn')} {name}  {str(detail)[:120]}")

    check("python>=3.9", sys.version_info >= (3, 9), rep["python"])
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    check("ffmpeg on PATH", bool(ff), ff or "not found — install FFmpeg 6+ and add to PATH")
    check("ffprobe on PATH", bool(fp), fp or "not found")
    if ff:
        _, out = sh(["ffmpeg", "-hide_banner", "-version"])
        ver = out.splitlines()[0] if out else "?"
        check("ffmpeg version", True, ver)
        _, filt = sh(["ffmpeg", "-hide_banner", "-filters"])
        for f, req in [("subtitles", True), ("xfade", True), ("loudnorm", True), ("silencedetect", True), ("afftdn", False),
                       ("gblur", False), ("tmix", False), ("blackdetect", True), ("freezedetect", False), ("sidechaincompress", False)]:
            check(f"filter {f}", f" {f} " in filt, "" if f" {f} " in filt else "missing in this FFmpeg build", required=req)
        _, xh = sh(["ffmpeg", "-hide_banner", "-h", "filter=xfade"])
        missing = [n for n in ("fade", "smoothleft", "smoothright", "smoothup", "zoomin", "hblur", "circleopen", "rectcrop", "wipeup", "fadeblack")
                   if f" {n} " not in xh]
        check("xfade transitions used by Skill 05", not missing, f"missing: {missing}" if missing else "all present")
        check("libass (ASS captions)", "--enable-libass" in out, "build has --enable-libass" if "--enable-libass" in out else "no libass: use overlay renderer path")
    try:
        import sae_fontmetrics
        f = sae_fontmetrics.load()
        miss = f.missing("Tiếng Việt: ắằẳẵặ ếềểễệ ốồổỗộ ớờởỡợ ứừửữự ỷỹỵ Đđ")
        check("bundled font Vietnamese coverage", not miss, f"missing {miss}" if miss else "Be Vietnam Pro OK")
    except Exception as e:  # noqa: BLE001
        check("bundled font", False, e)
    try:
        import cv2  # noqa: F401
        sys.path.insert(0, str(ROOT / "tools"))
        import subject_boxes
        try:
            subject_boxes.haar_path()
            check("OpenCV (optional face boxes)", True, f"cv2 {cv2.__version__} + Haar cascade")
        except RuntimeError as e:
            check("OpenCV (optional face boxes)", False, e, required=False)
    except ImportError:
        check("OpenCV (optional face boxes)", False, "not installed (optional): pip install opencv-python-headless", required=False)
    try:
        import jsonschema  # noqa: F401
        check("jsonschema (optional cross-check)", True, "installed", required=False)
    except ImportError:
        check("jsonschema (optional cross-check)", False, "not installed (optional)", required=False)
    if ff:
        import tempfile
        d = Path(tempfile.mkdtemp(prefix="sae_doctor_"))
        code, out = sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=1",
                        "-vf", f"subtitles=filename='{(ROOT / 'skills/02-smart-captions/examples/captions.example.ass').as_posix().replace(':', chr(92) + ':')}'"
                        f":fontsdir='{(ROOT / 'core/fonts').as_posix().replace(':', chr(92) + ':')}'",
                        "-frames:v", "10", str(d / "t.mp4")])
        check("burn ASS with bundled font (path escaping)", code == 0, out[-300:] if code else "ok")
    rep["ok"] = ok
    (ROOT / "doctor-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRESULT:", "READY" if ok else "NOT READY (see FAIL lines)", "-> doctor-report.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
