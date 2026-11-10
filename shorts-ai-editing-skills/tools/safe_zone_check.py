"""Draw platform UI safe zones on a frame of your video — compare with a phone screenshot of a real upload.

    python tools/safe_zone_check.py final.mp4 --at 3 --platforms tiktok,youtube-shorts --out check.png
    python tools/safe_zone_check.py screenshot.png --platforms tiktok        (works on images too)

Red = covered by that platform's UI (estimate from core/examples/platform-safe-zones.json),
green box = area used for captions/overlays (union of the chosen platforms). If your screenshot shows
buttons/text outside the red, edit the JSON numbers (fractions of width/height) and run again.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import sae_layout  # noqa: E402

COLORS = {"tiktok": "red", "youtube-shorts": "orange", "instagram-reels": "magenta", "facebook-reels": "purple"}


def build_filter(platforms, w=1080, h=1920) -> str:
    zones = sae_layout.load_zones()
    parts = [f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"]
    for p in platforms:
        z, c = zones[p], COLORS.get(p, "red")
        L, R, T, B = int(z["left"] * w), int(z["right"] * w), int(z["top"] * h), int(z["bottom"] * h)
        parts += [f"drawbox=x=0:y=0:w={w}:h={T}:color={c}@0.22:t=fill", f"drawbox=x=0:y={h - B}:w={w}:h={B}:color={c}@0.22:t=fill",
                  f"drawbox=x=0:y=0:w={L}:h={h}:color={c}@0.22:t=fill", f"drawbox=x={w - R}:y=0:w={R}:h={h}:color={c}@0.22:t=fill"]
    u = sae_layout.safe_area_for(platforms)
    parts.append(f"drawbox=x={int(u['left'] * w)}:y={int(u['top'] * h)}:w={int((1 - u['left'] - u['right']) * w)}:"
                 f"h={int((1 - u['top'] - u['bottom']) * h)}:color=lime@0.9:t=6")
    return ",".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--at", type=float, default=1.0, help="seconds (videos only)")
    ap.add_argument("--platforms", default="tiktok,youtube-shorts,instagram-reels")
    ap.add_argument("--out", default="safe-zone-check.png")
    a = ap.parse_args()
    plats = [p for p in a.platforms.split(",") if p]
    is_img = Path(a.input).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n"] + ([] if is_img else ["-ss", f"{a.at}"]) + \
          ["-i", a.input, "-frames:v", "1", "-vf", build_filter(plats), a.out]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-800:])
        return 1
    print(f"saved {a.out}  (usable area: {sae_layout.safe_area_for(plats)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
