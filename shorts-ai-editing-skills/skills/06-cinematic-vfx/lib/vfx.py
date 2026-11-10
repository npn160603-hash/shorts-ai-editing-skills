"""Skill 06 — Cinematic VFX (stdlib only). Base-layer effects only (never on captions, CR-04).

Every effect is a whitelisted FFmpeg filter template with numeric parameters — no free-form
filter strings, no code in JSON. Effects needing an overlay renderer (light sweep, masks,
animated reveals) are marked engine='overlay' and are NOT emitted for the FFmpeg path.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

# cost = relative render cost per affected second (1 = cheap global colour op)
CATALOG: Dict[str, Dict] = {
    "color-accent": {"engine": "ffmpeg", "cap": "vfx.colorAdjust", "cost": 1.0,
                     "params": {"contrast": (1.0, 1.15, 1.05), "saturation": (0.8, 1.3, 1.08), "brightness": (-0.05, 0.05, 0.0)}},
    "vignette":     {"engine": "ffmpeg", "cap": "vfx.colorAdjust", "cost": 1.0, "params": {"angle": (0.2, 0.8, 0.45)}},
    "soft-glow":    {"engine": "ffmpeg", "cap": "vfx.glow", "cost": 4.0,
                     "params": {"sigma": (6, 40, 18), "opacity": (0.05, 0.4, 0.2)}},
    "focus-blur":   {"engine": "ffmpeg", "cap": "vfx.blur", "cost": 2.5, "params": {"sigma": (2, 30, 10)}},
    "motion-blur":  {"engine": "ffmpeg", "cap": "vfx.motionBlur", "cost": 3.0, "params": {"frames": (2, 5, 3)}},
    "flash-accent": {"engine": "ffmpeg", "cap": "vfx.colorAdjust", "cost": 1.0, "params": {"brightness": (0.02, 0.12, 0.06)}},
    "light-sweep":  {"engine": "overlay", "cap": "overlay.alpha", "cost": 3.0, "params": {}},
    "mask-reveal":  {"engine": "overlay", "cap": "vfx.mask", "cost": 3.0, "params": {}},
}
INTENSITY_LIMITS = {"subtle": 1, "normal": 2, "dynamic": 4}  # max time-limited accents per video


def _p(effect: str, given: Dict) -> Dict:
    spec = CATALOG[effect]["params"]
    out = {}
    for k, (lo, hi, default) in spec.items():
        v = float(given.get(k, default))
        out[k] = max(lo, min(hi, v))
    return out


def plan_vfx(decisions: Dict, caps: Dict[str, str], intensity: str = "normal", global_grade: bool = True,
             hardware_budget: Optional[float] = None, duration: Optional[float] = None,
             forbidden: Sequence[str] = ()) -> Dict:
    ok = lambda e: caps.get(CATALOG[e]["cap"]) == "implemented" and e not in forbidden  # noqa: E731
    items: List[Dict] = []
    skipped: List[str] = []
    if global_grade and ok("color-accent"):
        items.append({"id": "fx01", "effect": "color-accent", "scope": "global", "startSec": 0.0,
                      "durationSec": duration or 0.0, "params": _p("color-accent", {}), "reason": "consistent look"})
    limit = INTENSITY_LIMITS[intensity]
    accents = [a for a in decisions.get("accents", []) if a["type"] in ("punch-in", "keyword-pop") and a.get("segmentId")]
    climax_ids = {s["segmentId"] for s in decisions.get("segments", []) if s["role"] == "climax"}
    sincere = [(s["startSec"], s["endSec"]) for s in decisions.get("segments", []) if s["captionMode"] == "calm"]
    used, last = 0, -1e9
    for a in accents:
        if a["segmentId"] not in climax_ids or used >= limit:
            continue
        if a["atSec"] - last < 2.0:
            skipped.append(f"vfx at {a['atSec']}: < 2 s after previous VFX accent")
            continue
        if any(x <= a["atSec"] < y for x, y in sincere):
            skipped.append(f"vfx at {a['atSec']}: sincere segment")
            continue
        eff = "soft-glow" if ok("soft-glow") else "flash-accent" if ok("flash-accent") else None
        if not eff:
            skipped.append("no VFX capability implemented for accents")
            break
        items.append({"id": f"fx{len(items) + 1:02d}", "effect": eff, "scope": "window", "startSec": round(a["atSec"], 3),
                      "durationSec": 0.4, "params": _p(eff, {}), "reason": f"climax accent ({a['type']})"})
        used += 1
        last = a["atSec"]
    cost = sum(CATALOG[i["effect"]]["cost"] * (i["durationSec"] or (duration or 0)) for i in items)
    per_sec = cost / duration if duration else 0.0
    if hardware_budget is not None and per_sec > hardware_budget:
        items = [i for i in items if i["scope"] == "global"]
        skipped.append(f"render cost {per_sec:.2f}/s exceeds budget {hardware_budget}: dropped window effects")
    return {"vfxPlanVersion": "1.0", "timebase": "output", "layer": "base-video-before-captions",
            "items": items, "estimatedCostPerSec": round(per_sec, 3), "skipped": skipped}


def ffmpeg_chain(plan: Dict) -> str:
    """Video filter (single input, single output) for FFmpeg items, applied before captions."""
    chain: List[str] = []
    for it in plan["items"]:
        e, p = it["effect"], it["params"]
        if CATALOG[e]["engine"] != "ffmpeg":
            continue
        a, b = it["startSec"], it["startSec"] + it["durationSec"]
        en = "" if it["scope"] == "global" else f":enable='between(t,{a:.3f},{b:.3f})'"
        if e == "color-accent":
            chain.append(f"eq=contrast={p['contrast']:.3f}:saturation={p['saturation']:.3f}:brightness={p['brightness']:.3f}{en}")
        elif e == "vignette":
            chain.append(f"vignette=angle={p['angle']:.3f}{en}")
        elif e == "focus-blur":
            chain.append(f"gblur=sigma={p['sigma']:.1f}{en}")
        elif e == "motion-blur":
            chain.append(f"tmix=frames={int(p['frames'])}{en}")
        elif e == "flash-accent":
            chain.append(f"eq=brightness={p['brightness']:.3f}{en}")
        elif e == "soft-glow":
            k = it["id"]
            chain.append(f"split[{k}a][{k}b];[{k}b]gblur=sigma={p['sigma']:.1f}[{k}g];"
                         f"[{k}a][{k}g]blend=all_mode=screen:all_opacity={p['opacity']:.3f}{en}")
    return ",".join(chain) if chain else "null"
