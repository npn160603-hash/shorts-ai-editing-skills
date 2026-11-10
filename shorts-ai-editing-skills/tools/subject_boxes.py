"""Optional subject (face) boxes for Skills 02/03/08 — needs `opencv-python` (Apache-2.0).

    pip install opencv-python-headless          # ~40 MB wheel, CPU only, no model download
    python tools/subject_boxes.py input.mp4 > subject-boxes.json

Detector order: YuNet (cv2.FaceDetectorYN) if you pass --yunet <model.onnx> (OpenCV Zoo model,
check its license), else the Haar cascade bundled inside opencv-python (no download).
Frames are decoded by FFmpeg (not cv2.VideoCapture) at `fps` samples/s, so codec support
matches the editor. Detections are tracked (IoU) into time ranges, expanded 15 % for hair/chin.
If OpenCV is missing, `available()` is False and callers must fall back (no boxes).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "lib"))

try:  # optional dependency
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None
    np = None


def available() -> bool:
    return cv2 is not None


def haar_path(custom: Optional[str] = None) -> str:
    """Bundled cascade of opencv-python 4.x wheels; some builds (e.g. contrib/5.x) omit it."""
    cand = [custom] if custom else []
    base = getattr(getattr(cv2, "data", None), "haarcascades", "") if cv2 else ""
    cand.append(str(Path(base) / "haarcascade_frontalface_default.xml"))
    for c in cand:
        if c and Path(c).is_file():
            return c
    raise RuntimeError("haarcascade_frontalface_default.xml not found in this OpenCV build: "
                       "install opencv-python-headless 4.x, pass --haar <file>, or use --yunet <model>")


def _frames(path: str, fps: float, width: int):
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height", "-of", "json", path], capture_output=True, text=True).stdout)
    sw, sh = probe["streams"][0]["width"], probe["streams"][0]["height"]
    h = int(round(sh * width / sw / 2) * 2)
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-vf", f"fps={fps},scale={width}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    size = width * h * 3
    n = 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield n / fps, np.frombuffer(buf, np.uint8).reshape(h, width, 3)
        n += 1
    p.wait()


def _iou(a, b) -> float:
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / max(a[2] * a[3] + b[2] * b[3] - inter, 1e-9)


def track(dets: Sequence[Dict], step: float, iou_min: float = 0.3, expand: float = 0.15) -> List[Dict]:
    """dets: [{t, box:(x,y,w,h) normalised, conf}] (largest face per sample) -> merged ranges."""
    out: List[Dict] = []
    cur = None
    for d in sorted(dets, key=lambda d: d["t"]):
        if cur and d["t"] - cur["last"] <= step * 2.5 and _iou(cur["box"], d["box"]) >= iou_min:
            n = cur["n"]
            cur["box"] = tuple((cur["box"][i] * n + d["box"][i]) / (n + 1) for i in range(4))  # running mean
            cur["n"] += 1
            cur["last"] = d["t"]
            cur["conf"] = max(cur["conf"], d.get("conf", 0.5))
        else:
            if cur:
                out.append(cur)
            cur = {"start": d["t"], "last": d["t"], "box": d["box"], "n": 1, "conf": d.get("conf", 0.5)}
    if cur:
        out.append(cur)
    res = []
    for c in out:
        x, y, w, h = c["box"]
        ex, ey = w * expand, h * expand
        x, y, w, h = max(0.0, x - ex), max(0.0, y - ey), min(1.0, w + 2 * ex), min(1.0, h + 2 * ey)
        res.append({"startSec": round(c["start"], 3), "endSec": round(c["last"] + step, 3),
                    "box": {"x": round(x, 4), "y": round(y, 4), "w": round(min(w, 1 - x), 4), "h": round(min(h, 1 - y), 4)},
                    "label": "face", "confidence": round(float(c["conf"]), 2)})
    return res


def detect(path: str, fps: float = 4.0, width: int = 360, yunet_model: Optional[str] = None,
           haar_file: Optional[str] = None) -> Dict:
    if not available():
        raise RuntimeError("OpenCV not installed: pip install opencv-python-headless (or skip subject boxes)")
    cascade = None if yunet_model else haar_path(haar_file)
    dets: List[Dict] = []
    yunet = None
    haar = None
    detector = "haar-frontalface"
    for t, img in _frames(path, fps, width):
        h, w = img.shape[:2]
        faces = []
        if yunet_model:
            if yunet is None:
                yunet = cv2.FaceDetectorYN.create(yunet_model, "", (w, h), 0.7)
                detector = "yunet"
            _, found = yunet.detect(img)
            for f in (found if found is not None else []):
                faces.append((float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[-1])))
        else:
            if haar is None:
                haar = cv2.CascadeClassifier(cascade)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            for (x, y, fw, fh) in haar.detectMultiScale(gray, 1.1, 5, minSize=(int(w * 0.08), int(w * 0.08))):
                faces.append((float(x), float(y), float(fw), float(fh), 0.6))
        if faces:
            x, y, fw, fh, c = max(faces, key=lambda f: f[2] * f[3])
            dets.append({"t": t, "box": (x / w, y / h, fw / w, fh / h), "conf": c})
    return {"subjectBoxesVersion": "1.0", "timebase": "source", "detector": detector, "sampleFps": fps,
            "boxes": track(dets, 1.0 / fps)}


def remap_to_output(sb: Dict, cut_list: Dict) -> Dict:
    """Source-time boxes -> output time through the Skill 04 cut list (pieces kept, never invented)."""
    from sae_timeline import keep_map_from_cutlist
    segs = keep_map_from_cutlist(cut_list)
    out = []
    for b in sb["boxes"]:
        for s in segs:
            lo, hi = max(b["startSec"], s.src_start), min(b["endSec"], s.src_end)
            if hi - lo > 0.05:
                out.append(dict(b, startSec=round(s.out_start + lo - s.src_start, 3), endSec=round(s.out_start + hi - s.src_start, 3)))
    return dict(sb, timebase="output", boxes=out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    model = sys.argv[sys.argv.index("--yunet") + 1] if "--yunet" in sys.argv else None
    haar = sys.argv[sys.argv.index("--haar") + 1] if "--haar" in sys.argv else None
    print(json.dumps(detect(sys.argv[1], yunet_model=model, haar_file=haar), indent=2))
