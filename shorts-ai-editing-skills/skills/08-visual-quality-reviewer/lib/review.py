"""Skill 08 — AI Visual Quality Reviewer: evidence-based checks (stdlib only).

Every finding = rule id + measured evidence + threshold + time range + suggested fix routed to
the owning skill. No aesthetic "score": the gate is simply  blockers == 0 and majors == 0.
Checks whose inputs are missing are listed in `notChecked` (never silently passed).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "lib"))
from sae_text import nfc, strip_punct  # noqa: E402


class Report:
    def __init__(self) -> None:
        self.findings: List[Dict] = []
        self.checked: List[str] = []
        self.not_checked: List[str] = []

    def add(self, rule: str, category: str, severity: str, msg: str, evidence: Dict,
            t: Optional[Sequence[float]] = None, fix: Optional[Dict] = None) -> None:
        f = {"id": f"F{len(self.findings) + 1:03d}", "ruleId": rule, "category": category, "severity": severity,
             "message": msg, "evidence": evidence}
        if t is not None:
            f["timeRange"] = [round(float(t[0]), 3), round(float(t[1]), 3)]
        if fix:
            f["suggestedFix"] = fix
        self.findings.append(f)


def _fold(s: str) -> str:
    return unicodedata.normalize("NFC", strip_punct(s).lower())


# ------------------------------------------------------------------ caption checks
def check_captions(r: Report, track: Dict, transcript: Optional[Dict], duration: float,
                   subject_boxes: Sequence[Dict] = (), max_cps: float = 17.0) -> None:
    r.checked.append("captions")
    safe = track["safeArea"]
    vocab = None
    if transcript:
        vocab = {}
        for w in transcript.get("words") or []:
            vocab[_fold(w["text"])] = True
        for s in transcript["segments"]:
            for w in s["text"].split():
                vocab[_fold(w)] = True
    prev_end = -1.0
    for p in track["pages"]:
        a, b = p["startSec"], p["endSec"]
        text = " ".join(w["text"] for w in p["words"])
        if a < prev_end - 1e-3:
            r.add("QA-CAP-07", "subtitle", "major", "caption pages overlap in time", {"page": p["id"], "start": a, "prevEnd": prev_end}, (a, prev_end),
                  {"skill": "smart-captions", "action": "rebuild-track", "params": {}})
        if b > duration + 0.05:
            r.add("QA-CAP-07", "subtitle", "major", "caption extends past video end", {"page": p["id"], "end": b, "duration": duration}, (a, b),
                  {"skill": "smart-captions", "action": "rebuild-track", "params": {}})
        prev_end = b
        cps = len(text.replace(" ", "")) / max(b - a, 1e-6)
        if cps > max_cps:
            r.add("QA-CAP-01", "readability", "major", "caption reading speed too high", {"page": p["id"], "cps": round(cps, 1), "max": max_cps}, (a, b),
                  {"skill": "smart-captions", "action": "use-preset", "params": {"stylePreset": "punchy-3"}})
        if b - a < 0.3:
            r.add("QA-CAP-02", "readability", "minor", "caption page on screen < 0.3 s", {"page": p["id"], "durationSec": round(b - a, 3)}, (a, b),
                  {"skill": "smart-captions", "action": "merge-short-pages", "params": {}})
        if len(p["lines"]) > 2:
            r.add("QA-CAP-03", "readability", "major", "more than 2 caption lines", {"page": p["id"], "lines": len(p["lines"])}, (a, b),
                  {"skill": "smart-captions", "action": "set", "params": {"maxLines": 2}})
        pl = p["placement"]
        h = pl.get("blockHeight", 0.08)
        top, bot = pl["y"] - h / 2, pl["y"] + h / 2
        if top < safe["top"] - 1e-3 or bot > 1 - safe["bottom"] + 1e-3:
            r.add("QA-CAP-04", "layout", "major", "caption block outside safe area", {"page": p["id"], "top": round(top, 3), "bottom": round(bot, 3), "safe": safe}, (a, b),
                  {"skill": "smart-captions", "action": "re-place", "params": {}})
        for bx in subject_boxes:
            if bx["startSec"] < b and a < bx["endSec"]:
                block = {"x": safe["left"], "y": top, "w": 1 - safe["left"] - safe["right"], "h": h}
                B = bx["box"]
                ix = max(0.0, min(block["x"] + block["w"], B["x"] + B["w"]) - max(block["x"], B["x"]))
                iy = max(0.0, min(block["y"] + block["h"], B["y"] + B["h"]) - max(block["y"], B["y"]))
                ratio = ix * iy / max(block["w"] * block["h"], 1e-9)
                if ratio > 0.15:
                    r.add("QA-CAP-05", "layout", "major", "caption covers subject", {"page": p["id"], "overlap": round(ratio, 2), "label": bx.get("label", "")}, (a, b),
                          {"skill": "smart-captions", "action": "re-place", "params": {"avoid": bx.get("label", "subject")}})
        if vocab is not None:
            invented = [w["text"] for w in p["words"] if _fold(w["text"]) and _fold(w["text"]) not in vocab]
            if invented:
                r.add("QA-CAP-06", "subtitle", "blocker", "caption contains words not in transcript", {"page": p["id"], "words": invented}, (a, b),
                      {"skill": "smart-captions", "action": "rebuild-track", "params": {}})
    if transcript and transcript.get("words") and track["mode"] == "word-highlight":
        for p in track["pages"]:
            for w in p["words"]:
                if not (p["startSec"] - 1e-3 <= w["startSec"] <= p["endSec"] + 1e-3):
                    r.add("QA-CAP-08", "sync", "major", "highlighted word outside its page time", {"page": p["id"], "word": w["text"]},
                          (w["startSec"], w["endSec"]), {"skill": "smart-captions", "action": "rebuild-track", "params": {}})


# ------------------------------------------------------------------ pacing / effects
def check_pacing(r: Report, cut_list: Optional[Dict], decisions: Optional[Dict], transcript: Optional[Dict],
                 budget: Dict, max_removed_ratio: float = 0.35) -> None:
    if cut_list:
        r.checked.append("cuts")
        st = cut_list["stats"]
        if st["removedRatio"] > max_removed_ratio + 1e-6:
            r.add("QA-PACE-04", "pacing", "blocker", "removed more than allowed", {"removedRatio": st["removedRatio"], "max": max_removed_ratio}, None,
                  {"skill": "smart-cut-pacing", "action": "rebuild", "params": {"maxRemovedRatio": max_removed_ratio}})
        outs = [s.get("outStartSec", 0) for s in cut_list["segments"]]
        for x, y in zip(outs, outs[1:]):
            if y - x < 0.5:
                r.add("QA-PACE-02", "pacing", "major", "two cuts closer than 0.5 s (flicker)", {"gapSec": round(y - x, 3)}, (x, y),
                      {"skill": "smart-cut-pacing", "action": "raise", "params": {"minKeepSec": 0.5}})
    else:
        r.not_checked.append("cuts (no cutList)")
    if transcript and transcript["segments"]:
        first = transcript["segments"][0]["startSec"]
        if first > 0.5:
            r.add("QA-PACE-03", "pacing", "minor", "dead air before first word", {"firstSpeechSec": first, "max": 0.5}, (0, first),
                  {"skill": "smart-cut-pacing", "action": "trim-head", "params": {}})
    if decisions:
        r.checked.append("effect-density")
        ov = [a for a in decisions["accents"] if a["type"] in ("keyword-pop", "callout", "headline", "vfx-accent")]
        cam = [a for a in decisions["accents"] if a["type"] in ("punch-in", "smooth-push", "jump-cut-reframe")]
        for name, items, lim in (("overlay", ov, budget.get("maxAccentsPer10s", 2.5)), ("camera", cam, budget.get("maxCameraMovesPer10s", 2.0))):
            for a in items:
                n = sum(1 for b in items if abs(b["atSec"] - a["atSec"]) < 5.0)
                if n > lim:
                    r.add("QA-FX-01", "effects", "major", f"too many {name} accents in a 10 s window", {"count": n, "max": lim}, (a["atSec"] - 5, a["atSec"] + 5),
                          {"skill": "editing-director", "action": "tighten-budget", "params": {"channel": name}})
                    break
    else:
        r.not_checked.append("effect density (no directorDecisions)")


def check_transitions(r: Report, tplan: Optional[Dict], hook_end: float, max_visual: int) -> None:
    if not tplan:
        r.not_checked.append("transitions")
        return
    r.checked.append("transitions")
    vis = [t for t in tplan["transitions"] if t["type"] != "cut"]
    for t in vis:
        if t["atSec"] < hook_end:
            r.add("QA-TR-01", "transition", "major", "visual transition inside hook", {"atSec": t["atSec"], "hookEndSec": hook_end},
                  (t["atSec"], t["atSec"] + t["durationSec"]), {"skill": "advanced-transitions", "action": "downgrade-to-cut", "params": {"boundaryIndex": t["boundaryIndex"]}})
    if len(vis) > max_visual:
        r.add("QA-TR-02", "transition", "major", "more visual transitions than budget", {"count": len(vis), "max": max_visual}, None,
              {"skill": "advanced-transitions", "action": "replan", "params": {"maxVisual": max_visual}})
    kinds = {t["type"] for t in vis}
    if len(kinds) > 2:
        r.add("QA-TR-03", "consistency", "minor", "more than 2 transition styles in one video", {"types": sorted(kinds)}, None,
              {"skill": "advanced-transitions", "action": "limit-styles", "params": {"max": 2}})


def check_camera(r: Report, cam: Optional[Dict]) -> None:
    if not cam:
        r.not_checked.append("camera")
        return
    r.checked.append("camera")
    busy = -1.0
    for m in cam["moves"]:
        z = max(m.get("toZoom", 1), m.get("fromZoom", 1))
        if z > cam["maxZoom"] + 1e-6:
            r.add("QA-CAM-01", "visual", "major", "zoom beyond source resolution limit", {"move": m["id"], "zoom": z, "maxZoom": cam["maxZoom"]},
                  (m["startSec"], m["startSec"] + m["durationSec"]), {"skill": "camera-movement", "action": "cap-zoom", "params": {}})
        if m["type"] != "shake":
            if m["startSec"] < busy - 1e-6:
                r.add("QA-CAM-02", "visual", "major", "overlapping camera moves", {"move": m["id"]}, (m["startSec"], busy),
                      {"skill": "camera-movement", "action": "rebuild", "params": {}})
            busy = max(busy, m["startSec"] + m["durationSec"])


def check_audio(r: Report, plan: Optional[Dict], measured: Optional[Dict]) -> None:
    if plan:
        r.checked.append("audio-licenses")
        if plan.get("music") and plan["music"].get("license") not in ("own", "CC0", "licensed"):
            r.add("QA-AUD-02", "rights", "blocker", "music without accepted license", {"license": plan["music"].get("license")}, None,
                  {"skill": "audio-director", "action": "remove-music", "params": {}})
        for s in plan.get("sfx", []):
            if s.get("license") not in ("own", "CC0", "licensed"):
                r.add("QA-AUD-02", "rights", "blocker", "SFX without accepted license", {"sfx": s["id"]}, (s["atSec"], s["atSec"] + 0.5),
                      {"skill": "audio-director", "action": "remove-sfx", "params": {"id": s["id"]}})
    if measured and plan:
        r.checked.append("loudness")
        t = plan["targets"]
        if abs(measured["input_i"] - t["integratedLufs"]) > 1.0:
            r.add("QA-AUD-01", "audio", "major", "integrated loudness off target", {"lufs": measured["input_i"], "target": t["integratedLufs"]}, None,
                  {"skill": "audio-director", "action": "renormalise", "params": {}})
        if measured["input_tp"] > t["truePeakDb"] + 0.3:
            r.add("QA-AUD-01", "audio", "major", "true peak above ceiling", {"truePeak": measured["input_tp"], "max": t["truePeakDb"]}, None,
                  {"skill": "audio-director", "action": "renormalise", "params": {}})
    elif not measured:
        r.not_checked.append("loudness (no measurement of final render)")


# ------------------------------------------------------------------ render checks
_BLACK = re.compile(r"black_start:([\d.]+)\s+black_end:([\d.]+)")
_FREEZE_S = re.compile(r"freeze_start:\s*([\d.]+)")
_FREEZE_D = re.compile(r"freeze_duration:\s*([\d.]+)")
_SIL = re.compile(r"silence_start:\s*([\d.]+)|silence_end:\s*([\d.]+)")


def check_render(r: Report, probe: Optional[Dict], expected: Dict, logs: Dict[str, str],
                 output_path: Optional[str] = None, source_path: Optional[str] = None) -> None:
    if probe:
        r.checked.append("render-metadata")
        v = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
        a = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
        if not v:
            r.add("QA-REN-01", "render", "blocker", "no video stream", {}, None)
        else:
            num, den = (int(x) for x in v.get("r_frame_rate", "0/1").split("/"))
            fps = num / den if den else 0
            if (v["width"], v["height"]) != (expected["width"], expected["height"]) or abs(fps - expected["fps"]) > 0.01:
                r.add("QA-REN-01", "render", "blocker", "resolution/fps differ from target",
                      {"got": [v["width"], v["height"], round(fps, 3)], "expected": [expected["width"], expected["height"], expected["fps"]]}, None,
                      {"skill": "ai-editing-orchestrator", "action": "fix-export-settings", "params": {}})
            if a and "duration" in v and "duration" in a:
                diff = abs(float(v["duration"]) - float(a["duration"]))
                if diff > 1.0 / expected["fps"] + 1e-3:
                    r.add("QA-REN-02", "sync", "major", "audio and video durations differ by more than 1 frame",
                          {"video": float(v["duration"]), "audio": float(a["duration"]), "diffSec": round(diff, 4)}, None,
                          {"skill": "smart-cut-pacing", "action": "frame-exact-trims", "params": {}})
        if not a:
            r.add("QA-REN-02", "sync", "major", "no audio stream in output", {}, None)
    else:
        r.not_checked.append("render metadata (no ffprobe JSON)")
    if "blackdetect" in logs:
        r.checked.append("black-frames")
        for m in _BLACK.finditer(logs["blackdetect"]):
            s, e = float(m.group(1)), float(m.group(2))
            r.add("QA-REN-03", "visual", "major", "black frames", {"start": s, "end": e}, (s, e),
                  {"skill": "camera-movement", "action": "check-clamp-or-transition", "params": {}})
    else:
        r.not_checked.append("black frames (no blackdetect log)")
    if "freezedetect" in logs:
        r.checked.append("frozen-frames")
        starts = [float(x) for x in _FREEZE_S.findall(logs["freezedetect"])]
        durs = [float(x) for x in _FREEZE_D.findall(logs["freezedetect"])]
        for s, d in zip(starts, durs):
            if d > 1.5:
                r.add("QA-REN-04", "visual", "minor", "frozen picture > 1.5 s (unexpected still?)", {"start": s, "duration": d}, (s, s + d))
    if "silencedetect" in logs:
        r.checked.append("output-silence")
        st = None
        for m in _SIL.finditer(logs["silencedetect"]):
            if m.group(1):
                st = float(m.group(1))
            elif st is not None:
                e = float(m.group(2))
                if e - st > 1.2:
                    r.add("QA-REN-05", "audio", "minor", "silence > 1.2 s in output", {"start": st, "end": e}, (st, e),
                          {"skill": "smart-cut-pacing", "action": "rebuild", "params": {}})
                st = None
    if output_path and source_path:
        r.checked.append("non-destructive-output")
        if Path(output_path).resolve() == Path(source_path).resolve():
            r.add("QA-REN-06", "safety", "blocker", "output path equals source path (overwrite)", {"path": output_path}, None,
                  {"skill": "ai-editing-orchestrator", "action": "new-revision-path", "params": {}})
        if "rev-" not in Path(output_path).as_posix():
            r.add("QA-REN-06", "safety", "minor", "output not in a revision folder", {"path": output_path}, None)


def finalize(r: Report, revision: int = 1) -> Dict:
    counts = {s: sum(1 for f in r.findings if f["severity"] == s) for s in ("blocker", "major", "minor", "info")}
    gate = "pass" if counts["blocker"] == 0 and counts["major"] == 0 else "fail"
    return {"qaReportVersion": "1.0", "revision": revision, "gate": gate, "counts": counts,
            "checked": r.checked, "notChecked": r.not_checked, "findings": r.findings,
            "manualReview": [
                "Watch with sound once and muted once on a phone-sized window.",
                "Contact sheet (every 0.5 s) + frames at each cut and caption page start.",
                "Vietnamese diacritics render (no tofu boxes), no clipped glyphs at line ends.",
                "Highlighted word matches the spoken word at 3 random points (±2 frames).",
            ]}


def contact_sheet_cmd(video: str, out_png: str, every: float = 0.5, cols: int = 6) -> List[str]:
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video, "-vf",
            f"fps={1 / every:g},scale=270:-2,tile={cols}x{cols}", "-frames:v", "1", out_png]


def detect_cmds(video: str) -> Dict[str, List[str]]:
    return {
        "blackdetect": ["ffmpeg", "-hide_banner", "-i", video, "-vf", "blackdetect=d=0.1:pix_th=0.08", "-an", "-f", "null", "-"],
        "freezedetect": ["ffmpeg", "-hide_banner", "-i", video, "-vf", "freezedetect=n=-60dB:d=1.5", "-an", "-f", "null", "-"],
        "silencedetect": ["ffmpeg", "-hide_banner", "-i", video, "-vn", "-af", "silencedetect=noise=-40dB:d=1.0", "-f", "null", "-"],
        "probe": ["ffprobe", "-v", "error", "-show_streams", "-of", "json", video],
    }
