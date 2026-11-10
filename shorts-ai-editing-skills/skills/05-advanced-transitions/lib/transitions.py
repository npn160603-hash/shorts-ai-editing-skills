"""Skill 05 — Advanced Video Transitions (stdlib only).

Key idea: transitions NEVER change output duration or move speech. A visual transition of
duration d at cut point b borrows d/2 "handle" frames from the removed (silent) material on
each side of the cut. No handle -> hard cut. Audio keeps the original cut (+ 10 ms fades, Skill 04/07).

plan_transitions()  boundaries -> TransitionPlan
ffmpeg_graph()      CutList + TransitionPlan -> filter_complex with [vout][aout]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "lib"))

# semantic type -> (ffmpeg xfade name, default duration). Only names present in FFmpeg >= 6.0.
CATALOG = {
    "cut":           (None, 0.0),
    "smooth-cut":    ("fade", 0.16),        # very short dissolve: softens a hard jump
    "swipe-left":    ("smoothleft", 0.30),  # "next item" / forward in a list
    "swipe-right":   ("smoothright", 0.30), # going back / comparison
    "swipe-up":      ("smoothup", 0.28),    # new section, vertical-native feel
    "zoom":          ("zoomin", 0.30),      # into climax / reveal
    "blur":          ("hblur", 0.24),       # time skip, soft topic change
    "mask-reveal":   ("circleopen", 0.35),  # reveal / before-after
    "shape-reveal":  ("rectcrop", 0.30),
    "directional-wipe": ("wipeup", 0.28),
    "dip-to-black":  ("fadeblack", 0.40),   # end of story / strong pause (rare in Shorts)
}
NEEDS_AI = {"motion-match": "needs motion vectors / optical flow or tracked object positions on both sides"}


def _speech_near(t: float, speech: Sequence[Sequence[float]], pad: float) -> bool:
    return any(a < t + pad and t - pad < b for a, b in speech)


def boundaries_from_cutlist(cut_list: Dict) -> List[Dict]:
    out, cursor = [], 0.0
    segs = cut_list["segments"]
    for i in range(1, len(segs)):
        a, b = segs[i - 1], segs[i]
        o = b.get("outStartSec")
        if o is None:
            o = sum(s["srcEndSec"] - s["srcStartSec"] for s in segs[:i])
        gap = b["srcStartSec"] - a["srcEndSec"]
        out.append({"index": i, "atSec": round(o, 4), "removedGapSec": round(max(gap, 0.0), 4),
                    "contiguousSource": gap >= 0})
    return out


def plan_transitions(cut_list: Dict, speech_out: Sequence[Sequence[float]], decisions: Optional[Dict] = None,
                     camera: Optional[Dict] = None, scene_changes_out: Sequence[float] = (),
                     max_visual: int = 2, xfade_available: bool = True, hook_end: float = 2.0,
                     forbidden: Sequence[str] = (), force_cut: Sequence[int] = (), max_styles: int = 2) -> Dict:
    roles = {}
    for s in (decisions or {}).get("segments", []):
        roles[round(s["startSec"], 2)] = s["role"]

    def role_after(t: float) -> Optional[str]:
        nxt = [s for s in (decisions or {}).get("segments", []) if s["startSec"] >= t - 0.6]
        return nxt[0]["role"] if nxt else None

    plan, used = [], 0
    cands = []
    for bd in boundaries_from_cutlist(cut_list):
        t = bd["atSec"]
        kind = "scene" if any(abs(t - s) < 0.1 for s in scene_changes_out) else "jump-cut"
        nxt_role = role_after(t)
        if kind == "jump-cut" and nxt_role in ("point", "climax", "cta", "payoff"):
            kind = "section"
        entry = {"boundaryIndex": bd["index"], "atSec": t, "kind": kind, "type": "cut", "durationSec": 0.0,
                 "handleSec": bd["removedGapSec"], "audio": "keep-cut", "reason": ""}
        want = {"jump-cut": "cut", "section": "swipe-up", "scene": "smooth-cut"}[kind]
        if nxt_role == "climax":
            want = "zoom"
        elif nxt_role == "point":
            want = "swipe-left"
        elif nxt_role == "cta":
            want = "smooth-cut"
        d = CATALOG[want][1]
        reasons = []
        if want == "cut":
            reasons.append("jump cut inside one shot: camera reframe hides it (no visual transition)")
        if t < hook_end:
            reasons.append("inside hook (CR-03)")
        if not xfade_available:
            reasons.append("no transition renderer (fallback hard cut)")
        if bd["index"] in force_cut:
            reasons.append("forced to cut by QA revision")
        if want in forbidden:
            reasons.append("forbidden by user")
        if want != "cut" and (bd["removedGapSec"] < d / 2 or not bd["contiguousSource"]):
            reasons.append(f"not enough handle: need {d / 2:.2f}s each side, have {bd['removedGapSec']:.2f}s")
        if want != "cut" and _speech_near(t, speech_out, d / 4):
            reasons.append("speech inside the central half of the transition window (CR-06)")
        if camera and want != "cut":
            for m in camera.get("moves", []):
                if m["type"] == "reframe-step" and abs(m["startSec"] - t) < 0.05:
                    continue
                if m["startSec"] < t + d / 2 and t - d / 2 < m["startSec"] + max(m["durationSec"], 0.04):
                    reasons.append(f"camera move {m['id']} in window (CR-02, camera wins)")
                    break
        if want == "cut" or reasons:
            entry["reason"] = "; ".join(reasons) or "hard cut"
            plan.append(entry)
            continue
        score = {"zoom": 0.9, "swipe-left": 0.7, "swipe-up": 0.6, "smooth-cut": 0.5}.get(want, 0.4)
        cands.append((score, entry, want, d))
        plan.append(entry)
    styles = set()
    for score, entry, want, d in sorted(cands, key=lambda x: -x[0]):
        if used >= max_visual:
            entry["reason"] = f"budget: maxVisualTransitions={max_visual}"
            continue
        if want not in styles and len(styles) >= max_styles:
            entry["reason"] = f"consistency: max {max_styles} transition styles per video"
            continue
        styles.add(want)
        entry.update(type=want, xfade=CATALOG[want][0], durationSec=d,
                     reason=f"{entry['kind']} boundary before {role_after(entry['atSec'])}; silent handles available")
        used += 1
    plan.sort(key=lambda e: e["atSec"])
    return {"transitionPlanVersion": "1.0", "timebase": "output", "transitions": plan,
            "visualCount": used, "notSupported": NEEDS_AI}


def ffmpeg_graph(cut_list: Dict, tplan: Dict, has_audio: bool = True, audio_fade_ms: float = 10.0) -> str:
    """Video: frame-exact trims with handles, grouped by concat, xfade between groups
    (duration-neutral). Audio: plain trim/concat with micro-fades — identical timing to the
    render without transitions. Source must be CFR. Labels: [vout][aout]."""
    fps = cut_list["fps"]
    segs = cut_list["segments"]
    tr = {t["boundaryIndex"]: t for t in tplan["transitions"] if t.get("xfade")}
    parts: List[str] = []
    ext = [[0, 0] for _ in segs]  # handle frames (head, tail)
    for bi, t in tr.items():
        h = int(round(t["durationSec"] * fps / 2))
        ext[bi - 1][1] = h
        ext[bi][0] = h
    groups: List[List[int]] = [[0]]
    for i in range(1, len(segs)):
        (groups.append([i]) if i in tr else groups[-1].append(i))
    glen = []
    for g_i, g in enumerate(groups):
        labels, frames = [], 0
        for i in g:
            n0 = int(round(segs[i]["srcStartSec"] * fps)) - ext[i][0]
            n1 = int(round(segs[i]["srcEndSec"] * fps)) + ext[i][1]
            parts.append(f"[0:v]trim=start_frame={n0}:end_frame={n1},setpts=PTS-STARTPTS[s{i}]")
            labels.append(f"[s{i}]")
            frames += n1 - n0
        head = "".join(labels) + (f"concat=n={len(labels)}:v=1:a=0," if len(labels) > 1 else "")
        parts.append(f"{head}settb=AVTB,fps={fps}[g{g_i}]")
        glen.append(frames)
    acc, cur = glen[0], "[g0]"
    for g_i in range(1, len(groups)):
        t = tr[groups[g_i][0]]
        dfr = 2 * int(round(t["durationSec"] * fps / 2))
        out = "[vout]" if g_i == len(groups) - 1 else f"[x{g_i}]"
        parts.append(f"{cur}[g{g_i}]xfade=transition={t['xfade']}:duration={dfr / fps:.6f}:offset={(acc - dfr) / fps:.6f}{out}")
        acc = acc + glen[g_i] - dfr
        cur = out
    if len(groups) == 1:
        parts.append("[g0]null[vout]")
    if has_audio:
        f = audio_fade_ms / 1000.0
        al = []
        for i, s in enumerate(segs):
            a, b = round(s["srcStartSec"] * fps) / fps, round(s["srcEndSec"] * fps) / fps
            parts.append(f"[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:st=0:d={f:.3f},afade=t=out:st={max(0.0, b - a - f):.6f}:d={f:.3f}[a{i}]")
            al.append(f"[a{i}]")
        parts.append("".join(al) + f"concat=n={len(al)}:v=0:a=1[aout]")
    return ";".join(parts)
