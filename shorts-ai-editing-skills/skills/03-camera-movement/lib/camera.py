"""Skill 03 — Cinematic Camera Movement (virtual camera on the base video), stdlib only.

Model: the virtual camera looks at a window of the (aspect-reframed) base frame.
  zoom z >= 1   : window size = 1/z of the base frame
  centre cx, cy : window centre in base-frame units [0..1]; clamped so the window never
                  leaves the frame (no black borders, ever).

build_track()     DirectorDecisions accents -> CameraTrack (moves, deterministic)
state_at()        CameraTrack, t -> (z, cx, cy)       (Remotion/Canvas adapters sample this)
ffmpeg_filter()   CameraTrack -> crop/scale/crop filter chain with per-frame expressions
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "lib"))

from sae_easing import EASE, EXPR as EASE_EXPR  # noqa: E402  (shared; includes back-out)
MAX_UPSCALE = 1.30  # beyond this, 1080p footage visibly softens


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def base_window(src_w: int, src_h: int, out_w: int, out_h: int) -> Tuple[int, int]:
    """Largest output-aspect window inside the source (even sizes)."""
    ar = out_w / out_h
    if src_w / src_h > ar:
        h = src_h
        w = int(round(h * ar))
    else:
        w = src_w
        h = int(round(w / ar))
    return w - w % 2, h - h % 2


def max_zoom(src_w: int, src_h: int, out_w: int, out_h: int, limit: float = 1.6) -> float:
    bw, bh = base_window(src_w, src_h, out_w, out_h)
    native = bh / out_h  # >=1 means the source has the resolution of the output (or more)
    return round(max(1.0, min(limit, native * MAX_UPSCALE)), 3)


# ------------------------------------------------------------------ track building
def _subject_center(t: float, boxes: Sequence[Dict]) -> Optional[Tuple[float, float]]:
    for b in boxes:
        if b["startSec"] <= t < b["endSec"]:
            x, y, w, h = b["box"]["x"], b["box"]["y"], b["box"]["w"], b["box"]["h"]
            return x + w / 2, y + h * 0.45  # eyes ≈ upper half of a face box
    return None


def _focus(z: float, subj: Optional[Tuple[float, float]]) -> Tuple[float, float]:
    """Centre that puts the subject on the upper-third line inside the zoomed window."""
    if subj is None:
        return 0.5, 0.45 if z > 1.0 else 0.5  # slight headroom bias for talking heads
    sx, sy = subj
    return sx, sy + (0.5 - 0.38) / z


def build_track(decisions: Dict, src: Dict, out: Dict, mode: str = "center-weighted",
                subject_boxes: Sequence[Dict] = (), cut_points: Sequence[float] = (),
                allow_shake: bool = False, seed: int = 7, zoom_scale: float = 1.0) -> Dict:
    zmax = max_zoom(src["width"], src["height"], out["width"], out["height"])
    moves: List[Dict] = []
    level, cx, cy = 1.0, 0.5, 0.5
    warnings = []
    if zmax <= 1.0:
        warnings.append("source has less resolution than the output window: zoom disabled (would blur)")
    use_subject = mode.startswith("subject-focus") and subject_boxes
    for a in sorted(decisions.get("accents", []), key=lambda x: x["atSec"]):
        if a["type"] not in ("smooth-push", "punch-in", "jump-cut-reframe"):
            continue
        z = min(1.0 + (a.get("zoom", 1.0) - 1.0) * zoom_scale, zmax)
        if a.get("zoom", 1.0) > zmax:
            warnings.append(f"{a['type']}@{a['atSec']}: zoom {a['zoom']} capped to {zmax} (source resolution)")
        subj = _subject_center(a["atSec"], subject_boxes) if use_subject else None
        ncx, ncy = _focus(z, subj)
        if a["type"] == "smooth-push":
            if "integer-crop" in mode and a["durationSec"] > 2.5:
                warnings.append("long slow push on integer-pixel engine may shimmer; keep ≤ 2.5 s or enable camera.subpixel")
            moves.append({"id": f"m{len(moves) + 1:02d}", "type": "smooth-zoom", "startSec": a["atSec"],
                          "durationSec": max(a["durationSec"], 0.3), "fromZoom": level, "toZoom": z,
                          "fromCenter": [cx, cy], "toCenter": [ncx, ncy], "easing": "ease-in-out",
                          "source": "director:smooth-push"})
        elif a["type"] == "punch-in":
            moves.append({"id": f"m{len(moves) + 1:02d}", "type": "punch-in", "startSec": a["atSec"], "durationSec": 0.0,
                          "fromZoom": level, "toZoom": z, "fromCenter": [cx, cy], "toCenter": [ncx, ncy],
                          "easing": "step", "source": "director:punch-in"})
            end = a["atSec"] + a["durationSec"]
            at_cut = any(abs(end - c) < 0.05 for c in cut_points)
            moves.append({"id": f"m{len(moves) + 1:02d}", "type": "punch-out", "startSec": round(end if at_cut else max(a["atSec"], end - 0.25), 4),
                          "durationSec": 0.0 if at_cut else 0.25, "fromZoom": z, "toZoom": 1.0,
                          "fromCenter": [ncx, ncy], "toCenter": [0.5, 0.5], "easing": "step" if at_cut else "ease-out",
                          "source": "director:punch-in(release)"})
            z, ncx, ncy = 1.0, 0.5, 0.5
        else:  # jump-cut-reframe: instant change exactly on the cut
            moves.append({"id": f"m{len(moves) + 1:02d}", "type": "reframe-step", "startSec": a["atSec"], "durationSec": 0.0,
                          "fromZoom": level, "toZoom": z, "fromCenter": [cx, cy], "toCenter": [ncx, ncy],
                          "easing": "step", "source": "director:jump-cut-reframe"})
        level, cx, cy = z, ncx, ncy
        if allow_shake and a["type"] == "punch-in" and decisions.get("intensity") == "dynamic":
            moves.append({"id": f"m{len(moves) + 1:02d}", "type": "shake", "startSec": a["atSec"], "durationSec": 0.3,
                          "amplitude": 0.006, "frequencyHz": 11.0, "seed": seed, "source": "director:impact"})
    moves.sort(key=lambda m: (m["startSec"], m["type"] == "shake"))
    # CR-01: drop moves that start inside a still-running non-instant move
    clean, busy_until = [], -1.0
    for m in moves:
        if m["type"] != "shake" and m["startSec"] < busy_until - 1e-6:
            warnings.append(f"{m['id']} dropped: overlaps a running move (CR-01)")
            continue
        clean.append(m)
        if m["type"] != "shake":
            busy_until = m["startSec"] + m["durationSec"]
    return {"cameraTrackVersion": "1.0", "timebase": "output", "mode": mode,
            "source": {"width": src["width"], "height": src["height"]},
            "output": {"width": out["width"], "height": out["height"], "fps": out["fps"]},
            "maxZoom": zmax, "seed": seed, "moves": clean, "warnings": warnings}


# ------------------------------------------------------------------ evaluation
def _window_clamp(z: float, cx: float, cy: float) -> Tuple[float, float]:
    half = 0.5 / z
    return clamp(cx, half, 1 - half), clamp(cy, half, 1 - half)


def _shake_offset(m: Dict, t: float) -> Tuple[float, float]:
    rng = random.Random(m["seed"])
    p1, p2, p3, p4 = (rng.uniform(0, 2 * math.pi) for _ in range(4))
    u = (t - m["startSec"]) / m["durationSec"]
    env = (1 - u) ** 2
    f, a = m["frequencyHz"], m["amplitude"]
    dx = a * env * (0.6 * math.sin(2 * math.pi * f * t + p1) + 0.4 * math.sin(2 * math.pi * f * 1.7 * t + p2))
    dy = a * env * (0.6 * math.sin(2 * math.pi * f * 0.9 * t + p3) + 0.4 * math.sin(2 * math.pi * f * 1.3 * t + p4))
    return dx, dy


def state_at(track: Dict, t: float) -> Tuple[float, float, float]:
    z, cx, cy = 1.0, 0.5, 0.5
    for m in track["moves"]:
        if m["type"] == "shake" or t < m["startSec"]:
            continue
        d = m["durationSec"]
        u = 1.0 if d <= 0 else clamp((t - m["startSec"]) / d, 0.0, 1.0)
        e = EASE[m["easing"]](u)
        z = m["fromZoom"] + (m["toZoom"] - m["fromZoom"]) * e
        cx = m["fromCenter"][0] + (m["toCenter"][0] - m["fromCenter"][0]) * e
        cy = m["fromCenter"][1] + (m["toCenter"][1] - m["fromCenter"][1]) * e
    for m in track["moves"]:
        if m["type"] == "shake" and m["startSec"] <= t < m["startSec"] + m["durationSec"]:
            dx, dy = _shake_offset(m, t)
            cx, cy = cx + dx, cy + dy
    cx, cy = _window_clamp(z, cx, cy)
    return round(z, 5), round(cx, 5), round(cy, 5)


def sample(track: Dict, duration: float) -> List[List[float]]:
    """Per-frame [frame, zoom, cx, cy] — for Remotion/Canvas adapters (subpixel transforms)."""
    fps = track["output"]["fps"]
    return [[n, *state_at(track, n / fps)] for n in range(int(round(duration * fps)))]


# ------------------------------------------------------------------ ffmpeg export
def _piecewise(track: Dict, key: str) -> str:
    """Build an ffmpeg expression in `t` for zoom ('z'), centre x ('cx') or y ('cy')."""
    idx = {"z": None, "cx": 0, "cy": 1}[key]
    expr = "1" if key == "z" else "0.5"
    for m in [m for m in track["moves"] if m["type"] != "shake"]:
        a = m["startSec"]
        v0 = m["fromZoom"] if idx is None else m["fromCenter"][idx]
        v1 = m["toZoom"] if idx is None else m["toCenter"][idx]
        if m["durationSec"] <= 0 or m["easing"] == "step":
            inner = f"{v1:.5f}"
        else:
            b = a + m["durationSec"]
            u = f"clip((t-{a:.4f})/{m['durationSec']:.4f},0,1)"
            inner = f"({v0:.5f}+({v1 - v0:.5f})*{EASE_EXPR[m['easing']].format(u=u)})"
        expr = f"if(lt(t,{a:.4f}),{expr},{inner})"
    if key != "z":
        for m in [m for m in track["moves"] if m["type"] == "shake"]:
            rng = random.Random(m["seed"])
            p = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
            f, amp, a, d = m["frequencyHz"], m["amplitude"], m["startSec"], m["durationSec"]
            env = f"pow(1-clip((t-{a:.4f})/{d:.4f},0,1),2)"
            if key == "cx":
                osc = f"(0.6*sin({2 * math.pi * f:.5f}*t+{p[0]:.5f})+0.4*sin({2 * math.pi * f * 1.7:.5f}*t+{p[1]:.5f}))"
            else:
                osc = f"(0.6*sin({2 * math.pi * f * 0.9:.5f}*t+{p[2]:.5f})+0.4*sin({2 * math.pi * f * 1.3:.5f}*t+{p[3]:.5f}))"
            expr = f"({expr}+if(between(t,{a:.4f},{a + d:.4f}),{amp}*{env}*{osc},0))"
    return expr


def ffmpeg_filter(track: Dict, reframe_cx: float = 0.5, reframe_cy: float = 0.5) -> str:
    """Video filter chain: static aspect reframe -> per-frame scale (zoom) -> fixed crop.
    Commas inside expressions are escaped for use inside -vf / -filter_complex."""
    sw, sh = track["source"]["width"], track["source"]["height"]
    ow, oh = track["output"]["width"], track["output"]["height"]
    bw, bh = base_window(sw, sh, ow, oh)
    bx = int(round(clamp(reframe_cx * sw - bw / 2, 0, sw - bw)))
    by = int(round(clamp(reframe_cy * sh - bh / 2, 0, sh - bh)))
    z = _piecewise(track, "z")
    cx, cy = _piecewise(track, "cx"), _piecewise(track, "cy")
    esc = lambda e: e.replace(",", "\\,")  # noqa: E731
    chain = []
    if (bw, bh) != (sw, sh):
        chain.append(f"crop={bw}:{bh}:{bx}:{by}")
    if (bw, bh) != (ow, oh):
        chain.append(f"scale={ow}:{oh}:flags=lanczos")
    chain.append(f"scale=w='trunc({ow}*({esc(z)})/2)*2':h='trunc({oh}*({esc(z)})/2)*2':eval=frame:flags=bicubic")
    chain.append(f"crop={ow}:{oh}:x='clip(({esc(cx)})*iw-{ow}/2\\,0\\,iw-{ow})':y='clip(({esc(cy)})*ih-{oh}/2\\,0\\,ih-{oh})'")
    chain.append("setsar=1")
    return ",".join(chain)
