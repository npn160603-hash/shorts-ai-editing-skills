"""Safe-area helpers. Union of several platforms = the strictest inset on each side."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

ZONES = Path(__file__).resolve().parents[1] / "examples" / "platform-safe-zones.json"


def load_zones(path=None) -> Dict[str, Dict]:
    return json.loads(Path(path or ZONES).read_text(encoding="utf-8"))["platforms"]


def safe_area_for(platforms: Iterable[str], path=None) -> Dict[str, float]:
    z = load_zones(path)
    ps = list(platforms) or list(z)
    unknown = [p for p in ps if p not in z]
    if unknown:
        raise KeyError(f"unknown platform(s) {unknown}; known: {sorted(z)}")
    return {k: max(z[p][k] for p in ps) for k in ("left", "right", "top", "bottom")}


def safe_center_x(safe: Dict[str, float]) -> float:
    """Horizontal centre of the usable area (asymmetric when right-side buttons are wider)."""
    return (safe["left"] + 1 - safe["right"]) / 2
