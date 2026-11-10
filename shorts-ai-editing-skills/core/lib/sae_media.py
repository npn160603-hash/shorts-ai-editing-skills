"""Media probing + VFR detection/normalisation (FFmpeg/ffprobe, stdlib only).

Frame-exact cutting (Skills 04/05) requires constant frame rate. Phone footage is often VFR.
`probe_media()` reports fps facts; `is_vfr()` decides with a frame-timestamp sample;
`normalize_cmd()` builds a non-destructive CFR conversion (new file, audio copied when possible).
"""
from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from typing import Dict, List, Optional


def _run(cmd: List[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-800:]}")
    return r.stdout


def _rate(s: str) -> float:
    try:
        f = Fraction(s)
        return float(f) if f else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe_media(path: str) -> Dict:
    data = json.loads(_run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        raise ValueError("no video stream")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = v["width"], v["height"]
    if abs(rot) in (90, 270):
        w, h = h, w
    return {"width": w, "height": h, "rotation": rot,
            "rFrameRate": _rate(v.get("r_frame_rate", "0/1")), "avgFrameRate": _rate(v.get("avg_frame_rate", "0/1")),
            "durationSec": float(data["format"].get("duration", v.get("duration", 0)) or 0),
            "videoCodec": v.get("codec_name"), "pixFmt": v.get("pix_fmt"),
            "hasAudio": a is not None, "audioCodec": a.get("codec_name") if a else None,
            "sampleRate": int(a["sample_rate"]) if a and a.get("sample_rate") else None}


def frame_intervals(path: str, max_frames: int = 600) -> List[float]:
    out = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time,best_effort_timestamp_time",
                "-read_intervals", f"%+#{max_frames}", "-of", "csv=p=0", path])
    ts = []
    for line in out.splitlines():
        vals = [x for x in line.split(",") if x and x != "N/A"]
        if vals:
            ts.append(float(vals[0]))
    ts.sort()
    return [b - a for a, b in zip(ts, ts[1:]) if b > a]


def is_vfr(path: str, tolerance: float = 0.15) -> Dict:
    """VFR if r_frame_rate and avg_frame_rate disagree, or frame intervals vary more than
    `tolerance` (relative) on > 2% of sampled frames."""
    info = probe_media(path)
    iv = frame_intervals(path)
    reasons = []
    if info["rFrameRate"] and info["avgFrameRate"] and abs(info["rFrameRate"] - info["avgFrameRate"]) / info["rFrameRate"] > 0.01:
        reasons.append(f"r_frame_rate {info['rFrameRate']:.3f} != avg_frame_rate {info['avgFrameRate']:.3f}")
    if iv:
        med = sorted(iv)[len(iv) // 2]
        odd = sum(1 for d in iv if abs(d - med) / med > tolerance)
        if odd > 0.02 * len(iv):
            reasons.append(f"{odd}/{len(iv)} frame intervals deviate > {int(tolerance * 100)}% from median {med:.4f}s")
    return {"vfr": bool(reasons), "reasons": reasons, "probe": info}


def normalize_cmd(src: str, dst: str, fps: float = 30.0, width: Optional[int] = None, height: Optional[int] = None,
                  crf: int = 18, copy_audio: bool = True) -> List[str]:
    """CFR (and optional size) normalisation to a NEW file. Never pass dst == src."""
    if src == dst:
        raise ValueError("refusing to overwrite the source file")
    vf = [f"fps={fps:g}"]
    if width and height:
        vf.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
    cmd = ["ffmpeg", "-hide_banner", "-n", "-i", src, "-vf", ",".join(vf), "-fps_mode", "cfr",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "copy"] if copy_audio else ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    return cmd + [dst]
