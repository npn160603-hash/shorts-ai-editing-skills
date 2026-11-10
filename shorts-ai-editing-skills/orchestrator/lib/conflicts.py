"""Cross-skill conflict check — the single place where CR-01 … CR-10 are enforced.

resolve(sections, ctx) mutates copies of the sections and returns (sections, log).
Priority (high -> low): speech/audio integrity > caption readability > subject visibility >
hook > camera > transitions > VFX > SFX. The lower-priority item is DROPPED or DOWNGRADED,
never silently moved, and every action is logged.
"""
from __future__ import annotations

import copy
from typing import Dict, List, Tuple

COMPOSITE_ORDER = ["base-video", "camera", "vfx(base layer)", "captions", "overlays(motionPlan)"]


def _log(log: List[Dict], rule: str, action: str, target: str, detail: str) -> None:
    log.append({"rule": rule, "action": action, "target": target, "detail": detail})


def _speech(sections: Dict) -> List[Tuple[float, float]]:
    tr = sections.get("transcript") or {}
    if tr.get("words"):
        return [(w["startSec"], w["endSec"]) for w in tr["words"]]
    return [(s["startSec"], s["endSec"]) for s in tr.get("segments", [])]


def resolve(sections: Dict, ctx: Dict) -> Tuple[Dict, List[Dict]]:
    s = copy.deepcopy(sections)
    log: List[Dict] = []
    hook = ctx.get("hookEndSec", 2.0)
    budget = ctx.get("effectBudget", {})
    speech = _speech(s)
    cam, tp, dd = s.get("cameraTrack"), s.get("transitionPlan"), s.get("directorDecisions")
    fx, am, tk = s.get("vfxPlan"), s.get("audioMixPlan"), s.get("captionTrack")

    # CR-08 ownership
    owners = ctx.get("owners", {})
    for name, owner in ctx.get("producedBy", {}).items():
        if owners.get(name) and owners[name] != owner:
            _log(log, "CR-08", "error", name, f"written by {owner}, owner is {owners[name]}")

    # CR-01 camera overlap
    if cam:
        keep, busy = [], -1.0
        for m in sorted(cam["moves"], key=lambda m: m["startSec"]):
            if m["type"] != "shake" and m["startSec"] < busy - 1e-6:
                _log(log, "CR-01", "drop", f"camera:{m['id']}", "starts while another move runs")
                continue
            keep.append(m)
            if m["type"] != "shake":
                busy = m["startSec"] + m["durationSec"]
        cam["moves"] = keep

    # CR-03 / CR-02 / CR-06 on transitions
    if tp:
        for t in tp["transitions"]:
            if t["type"] == "cut":
                continue
            a, b = t["atSec"] - t["durationSec"] / 2, t["atSec"] + t["durationSec"] / 2
            why = None
            if t["atSec"] < hook:
                why = ("CR-03", "inside hook")
            elif any(x < t["atSec"] + t["durationSec"] / 4 and t["atSec"] - t["durationSec"] / 4 < y for x, y in speech):
                why = ("CR-06", "speech in central half of window")
            elif cam:
                for m in cam["moves"]:
                    if m["type"] == "reframe-step" and abs(m["startSec"] - t["atSec"]) < 0.05:
                        continue
                    if m["startSec"] < b and a < m["startSec"] + max(m["durationSec"], 0.04):
                        why = ("CR-02", f"camera move {m['id']} in window (camera wins)")
                        break
            if why:
                _log(log, why[0], "downgrade-to-cut", f"transition:{t['boundaryIndex']}", why[1])
                t.update(type="cut", durationSec=0.0, reason=f"{t['reason']} | conflict-check: {why[1]}")
                t.pop("xfade", None)
        tp["visualCount"] = sum(1 for t in tp["transitions"] if t["type"] != "cut")

    # CR-05 overlay budget (re-count after everything else)
    if dd:
        lim = budget.get("maxAccentsPer10s", dd["effectBudget"].get("maxAccentsPer10s", 2.5))
        ov = [a for a in dd["accents"] if a["type"] in ("keyword-pop", "callout", "headline", "vfx-accent")]
        for a in sorted(ov, key=lambda x: x["score"]):  # drop lowest score first
            n = sum(1 for b in ov if abs(b["atSec"] - a["atSec"]) < 5.0 and b in dd["accents"])
            if n > lim:
                dd["accents"].remove(a)
                dd.setdefault("dropped", []).append(dict(a, droppedBecause="conflict-check CR-05"))
                _log(log, "CR-05", "drop", f"accent:{a['type']}@{a['atSec']}", f"{n} overlay accents in 10 s > {lim}")

    # CR-03 / CR-04 on VFX
    if fx:
        if fx.get("layer") != "base-video-before-captions":
            _log(log, "CR-04", "error", "vfxPlan", "VFX must apply to the base layer before captions")
        keep = []
        for it in fx["items"]:
            if it["scope"] == "window" and it["startSec"] < hook:
                _log(log, "CR-03", "drop", f"vfx:{it['id']}", "inside hook")
                continue
            if it["scope"] == "window" and tp and any(t["type"] != "cut" and abs(t["atSec"] - it["startSec"]) < 0.5 for t in tp["transitions"]):
                _log(log, "CR-08", "drop", f"vfx:{it['id']}", "coincides with a visual transition (VFX has lower priority)")
                continue
            keep.append(it)
        fx["items"] = keep

    # CR-07 SFX anchors must still exist; gain under speech
    if am and am.get("sfx"):
        vis = {str(t["boundaryIndex"]) for t in (tp or {}).get("transitions", []) if t["type"] != "cut"}
        pops = {round(a["atSec"], 2) for a in (dd or {}).get("accents", []) if a["type"] in ("keyword-pop", "callout")}
        keep = []
        for e in am["sfx"]:
            anc = e["anchor"]
            alive = (anc["type"] == "transition" and anc["ref"] in vis) or \
                    (anc["type"] in ("keyword-pop", "callout") and any(abs(p - e["atSec"]) < 0.2 for p in pops))
            if not alive:
                _log(log, "CR-07", "drop", f"sfx:{e['id']}", "its visual anchor was removed")
                continue
            over = any(x < e["atSec"] + 0.4 and e["atSec"] < y for x, y in speech)
            if over and e["gainDb"] > -12:
                _log(log, "CR-07", "lower-gain", f"sfx:{e['id']}", f"{e['gainDb']} dB -> -12 dB (over speech)")
                e["gainDb"] = -12.0
            keep.append(e)
        am["sfx"] = keep

    # CR-09 captions vs subject boxes (report; the fix belongs to smart-captions)
    if tk:
        for p in tk["pages"]:
            for bx in ctx.get("subjectBoxes", []):
                if bx["startSec"] < p["endSec"] and p["startSec"] < bx["endSec"]:
                    h = p["placement"].get("blockHeight", 0.08)
                    top, bot = p["placement"]["y"] - h / 2, p["placement"]["y"] + h / 2
                    B = bx["box"]
                    iy = max(0.0, min(bot, B["y"] + B["h"]) - max(top, B["y"]))
                    if iy / max(h, 1e-6) > 0.15 and B["w"] > 0.05:
                        _log(log, "CR-09", "report", f"caption:{p['id']}", "overlaps subject box; QA will route to smart-captions")
                        break

    # CR-10 determinism & non-destructive output
    if cam and "seed" not in cam:
        _log(log, "CR-10", "error", "cameraTrack", "missing seed")
    out = ctx.get("outputPath", "")
    if out and ("rev-" not in out.replace("\\", "/") or out == ctx.get("sourcePath")):
        _log(log, "CR-10", "error", "output", f"output path must be a new revision path: {out}")

    s["_compositeOrder"] = COMPOSITE_ORDER
    return s, log
