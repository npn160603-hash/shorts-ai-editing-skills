"""Graphic overlays rendered through libass (FFmpeg path) — the renderer V1.1 described but never shipped.

Layers (all optional, all text taken from the transcript / director / user — never invented):
  hook title      : big boxed headline during the hook (user text, else the hook's keyword)
  keyword callout : keyword-pop accents from Skill 01 as a popping card (upper third)
  progress bar    : thin bar growing across the top edge for the whole video
  CTA card        : user-supplied CTA text in the last seconds (no default wording)

`overlay_events()` returns ASS style lines + dialogue lines; `merge_into_ass()` appends them to the
caption ASS so one `subtitles=` pass draws everything (captions stay on the highest layer).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import captions as C  # caption helpers: _ass_time, _ass_color, _ass_escape, resolve_font, load_presets

DEFAULTS = {"hookTitle": "auto", "keywordCallouts": True, "progressBar": True, "cta": None,
            "accent": "#FFD400", "boxColor": "#111111", "barColor": "#FFD400", "ctaSec": 2.2}


def _hook_title(decisions: Optional[Dict], user: Optional[str]) -> Optional[str]:
    if user and user != "auto":
        return user
    if user is None or not decisions:
        return None
    hook_end = decisions["hookEndSec"]
    for a in decisions.get("accents", []):
        if a["type"] == "keyword-pop" and a["atSec"] < hook_end and a.get("target"):
            return a["target"]
    return None


def overlay_events(track: Dict, decisions: Optional[Dict], duration: float, opts: Optional[Dict] = None,
                   presets: Optional[Dict] = None) -> Tuple[List[str], List[str], Dict]:
    o = dict(DEFAULTS, **(opts or {}))
    st = (presets or C.load_presets())[track["stylePreset"]]
    W, H = track["video"]["width"], track["video"]["height"]
    safe = track["safeArea"]
    fm = C.resolve_font(st)
    size = lambda em: round(fm.ass_size_for_em(em), 1) if fm else em  # noqa: E731
    font = st["fontFamily"]
    acc, box, bar = C._ass_color(o["accent"]), C._ass_color(o["boxColor"], 40), C._ass_color(o["barColor"])
    cx = int(round((safe["left"] + 1 - safe["right"]) / 2 * W))
    styles = [
        f"Style: OvHook,{font},{size(st['fontSize'] * 1.15)},&H00111111,&H00111111,{acc},{acc},-1,0,0,0,100,100,0,0,3,18,0,8,0,0,0,1",
        f"Style: OvCallout,{font},{size(st['fontSize'] * 1.45)},{acc},{acc},&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,0,0,0,1",
        f"Style: OvCta,{font},{size(st['fontSize'] * 0.9)},&H00FFFFFF,&H00FFFFFF,{box},{box},-1,0,0,0,100,100,0,0,3,16,0,2,0,0,0,1",
        f"Style: OvBar,{font},10,{bar},{bar},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
    ]
    ev: List[str] = []
    used = {"hookTitle": None, "callouts": 0, "progressBar": False, "cta": None}
    hook_end = decisions["hookEndSec"] if decisions else min(2.0, duration)
    title = _hook_title(decisions, o["hookTitle"])
    if title:
        y = int(round((safe["top"] + 0.06) * H))
        txt = C._ass_escape(title.upper())
        ev.append(f"Dialogue: 2,{C._ass_time(0)},{C._ass_time(hook_end)},OvHook,,0,0,0,,"
                  f"{{\\an8\\pos({cx},{y})\\fscx80\\fscy80\\t(0,120,\\fscx106\\fscy106)\\t(120,200,\\fscx100\\fscy100)\\fad(60,120)}}{txt}")
        used["hookTitle"] = title
    if o["keywordCallouts"] and decisions:
        y = int(round(0.24 * H))
        for a in decisions.get("accents", []):
            if a["type"] != "keyword-pop" or not a.get("target") or a["atSec"] < hook_end:
                continue
            t0, t1 = a["atSec"], min(duration, a["atSec"] + max(0.7, a.get("durationSec", 0.8)))
            ev.append(f"Dialogue: 2,{C._ass_time(t0)},{C._ass_time(t1)},OvCallout,,0,0,0,,"
                      f"{{\\an5\\pos({cx},{y})\\fscx70\\fscy70\\t(0,110,\\fscx108\\fscy108)\\t(110,190,\\fscx100\\fscy100)"
                      f"\\fad(40,140)}}{C._ass_escape(a['target'].upper())}")
            used["callouts"] += 1
    if o["progressBar"] and duration > 0:
        hpx = max(6, int(round(H * 0.005)))
        ms = int(round(duration * 1000))
        ev.append(f"Dialogue: 0,{C._ass_time(0)},{C._ass_time(duration)},OvBar,,0,0,0,,"
                  f"{{\\an7\\pos(0,0)\\p1\\clip(0,0,0,{hpx})\\t(0,{ms},\\clip(0,0,{W},{hpx}))}}m 0 0 l {W} 0 {W} {hpx} 0 {hpx}{{\\p0}}")
        used["progressBar"] = True
    if o["cta"]:
        t0 = max(hook_end, duration - o["ctaSec"])
        y = int(round((1 - safe["bottom"] - 0.02) * H))
        ev.append(f"Dialogue: 2,{C._ass_time(t0)},{C._ass_time(duration)},OvCta,,0,0,0,,"
                  f"{{\\an2\\fad(150,0)\\move({cx},{y + 40},{cx},{y},0,180)}}{C._ass_escape(o['cta'])}")
        used["cta"] = o["cta"]
    return styles, ev, used


def merge_into_ass(ass_text: str, styles: List[str], events: List[str]) -> str:
    """Insert overlay styles after the caption style and overlay events before caption events
    (captions are Layer 1 and drawn after layer 0; overlays on layer 2 sit above captions only
    where they do not overlap — callouts/hook live in the upper third, captions lower)."""
    lines = ass_text.rstrip("\n").split("\n")
    i = max(k for k, ln in enumerate(lines) if ln.startswith("Style:"))
    lines[i + 1:i + 1] = styles
    j = next(k for k, ln in enumerate(lines) if ln.startswith("Format: Layer"))
    lines[j + 1:j + 1] = events
    return "\n".join(lines) + "\n"
