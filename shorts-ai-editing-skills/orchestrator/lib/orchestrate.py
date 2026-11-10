"""AI Editing Orchestrator — deterministic planner (stdlib only).

Input : EditRequest + CapabilityManifest + SkillRegistry
Output: OrchestrationPlan (which skills run, mode, order, budgets, gates)

An LLM MAY be used upstream to turn free text into `intent`, but this planner never
needs one: it has a VI/EN keyword parser as fallback, and every decision is
reproducible from the three input files.

CLI:  python orchestrate.py request.json manifest.json registry.json > plan.json
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "lib"))
from sae_schema import load_json, validate  # noqa: E402

BUDGETS = {
    "subtle":  {"maxAccentsPer10s": 1.5, "minGapBetweenAccentsSec": 2.5, "maxCameraMovesPer10s": 1.0, "maxVisualTransitions": 1, "maxSfxPer10s": 1.0},
    "normal":  {"maxAccentsPer10s": 2.5, "minGapBetweenAccentsSec": 1.6, "maxCameraMovesPer10s": 2.0, "maxVisualTransitions": 2, "maxSfxPer10s": 2.0},
    "dynamic": {"maxAccentsPer10s": 4.0, "minGapBetweenAccentsSec": 1.0, "maxCameraMovesPer10s": 3.5, "maxVisualTransitions": 4, "maxSfxPer10s": 3.5},
}

# keyword -> intent flags. Matched on accent-folded, lower-cased text.
_KEYWORDS: List[Tuple[str, Dict]] = [
    (r"\b(cat|bo doan|doan thua|khoang lang|im lang|silence|cut|trim|tighten|jump ?cut|rut gon)s?\b", {"cut": True}),
    (r"\b(phu de|sub|subtitle|caption|chu dong|karaoke)s?\b", {"captions": True}),
    (r"\b(zoom|phong to|pan|camera|reframe|punch ?in|can canh)s?\b", {"camera": True}),
    (r"\b(chuyen canh|transition|swipe|wipe)s?\b", {"transitions": True}),
    (r"\b(vfx|glow|phat sang|light sweep|anh sang quet|hieu ung dac biet|lens flare)s?\b", {"vfx": True}),
    (r"\b(giong|am thanh|voice|audio|loudness|to nho|ro tieng|ro loi)s?\b", {"audio": True}),
    (r"\b(giu giong noi ro|giong noi ro|ro giong|clear voice|clean voice|speech clarity)s?\b", {"speechPriority": True, "audio": True}),
    (r"\b(nhac nen|nhac|music|bgm|ducking)s?\b", {"music": True, "audio": True}),
    (r"\b(sfx|sound effect|whoosh|am thanh hieu ung|tieng dong)s?\b", {"sfx": True, "audio": True}),
    (r"\b(chuyen nghiep|professional|pro)s?\b", {"style": "professional"}),
    (r"\b(toi gian|minimal|don gian)s?\b", {"style": "minimal", "intensity": "subtle"}),
    (r"\b(soi dong|nang dong|manh|dynamic|energetic|hype|nhanh)s?\b", {"style": "energetic", "intensity": "dynamic"}),
    (r"\b(nhe nhang|tinh te|subtle|nhe)s?\b", {"intensity": "subtle"}),
    (r"\b(vua phai|moderate|vua du|can bang|balanced)s?\b", {"intensity": "normal"}),
]


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse_intent(text: str) -> Dict:
    t = fold(text)
    intent: Dict = {}
    for pat, flags in _KEYWORDS:
        if re.search(pat, t):
            for k, v in flags.items():
                if k == "intensity" and "intensity" in intent:
                    continue  # first explicit intensity wins ("vua phai" before "manh" in a later clause)
                intent[k] = v
    intent.setdefault("intensity", "normal")
    intent.setdefault("style", "professional")
    for k in ("cut", "captions", "camera", "transitions", "vfx", "audio", "sfx", "music", "speechPriority"):
        intent.setdefault(k, False)
    # A professional Short always gets basic audio hygiene and a restrained transition pass.
    if intent["style"] in ("professional", "energetic"):
        intent["audio"] = True
        intent["transitions"] = intent["transitions"] or intent["cut"]
    return intent


def _cap(manifest: Dict, key: str) -> str:
    return manifest["capabilities"].get(key, {}).get("status", "missing")


_SKILL_INTENT = {
    "smart-cut-pacing": "cut", "smart-captions": "captions", "camera-movement": "camera",
    "advanced-transitions": "transitions", "cinematic-vfx": "vfx", "audio-director": "audio",
}
_ALWAYS = {"ai-editing-orchestrator", "editing-director", "visual-quality-reviewer", "shorts-motion-designer"}


def _mode(skill_id: str, m: Dict, intent: Dict, request: Dict) -> Tuple[str, bool, List[str]]:
    """Return (mode, degraded?, notes)."""
    c = lambda k: _cap(m, k) == "implemented"  # noqa: E731
    forb = set(request.get("constraints", {}).get("forbiddenEffects", []))
    notes: List[str] = []
    if skill_id == "smart-cut-pacing":
        parts = []
        if c("analysis.silenceDetect"):
            parts.append("silence-signal")
        if c("transcript.wordTimestamps"):
            parts.append("word-gaps")
        if c("analysis.semanticLLM"):
            parts.append("semantic")
        if not parts:
            return "none", True, ["no silence detector and no word timestamps: cannot cut safely"]
        return "+".join(parts), "silence-signal" not in parts, notes
    if skill_id == "editing-director":
        return ("heuristic+llm" if c("analysis.semanticLLM") else "heuristic"), False, notes
    if skill_id == "smart-captions":
        words = c("transcript.wordTimestamps")
        mode = ("word-highlight" if words else "phrase")
        mode += ";" + ("ass" if c("overlay.assSubtitles") else "overlay-text")
        mode += ";" + ("subject-aware" if c("analysis.subjectBoxes") else "safe-zone")
        if not words:
            notes.append("no reliable word timestamps: phrase-level captions, no per-word highlight")
        return mode, not words, notes
    if skill_id == "camera-movement":
        mode = "subject-focus" if c("analysis.subjectBoxes") else "center-weighted"
        if "camera-shake" in forb or intent.get("style") == "minimal":
            mode += ";no-shake"
        if not c("camera.subpixel"):
            mode += ";integer-crop"
            notes.append("integer-pixel crop: prefer punch-in (instant) over slow push-in to avoid jitter")
        return mode, not c("analysis.subjectBoxes"), notes
    if skill_id == "advanced-transitions":
        if c("transition.xfade") or c("transition.custom"):
            return "restrained", False, notes
        return "hard-cut-only", True, ["no transition renderer: hard cuts + audio micro-crossfade only"]
    if skill_id == "audio-director":
        parts = [k.split(".")[1] for k in ("audio.loudnorm", "audio.crossfade", "audio.denoise", "audio.duck", "audio.mixSfx") if c(k)]
        if not intent.get("music") or not request.get("constraints", {}).get("allowMusic", False):
            parts = [p for p in parts if p != "duck"]
        if not intent.get("sfx") or not request.get("constraints", {}).get("allowSfx", False):
            parts = [p for p in parts if p != "mixSfx"]
        return ("speech-first;" + "+".join(parts)) if parts else "measure-only", not c("audio.loudnorm"), notes
    if skill_id == "cinematic-vfx":
        parts = [k.split(".")[1] for k in ("vfx.colorAdjust", "vfx.blur", "vfx.glow", "vfx.mask", "vfx.motionBlur") if c(k)]
        return ("tiered:" + "+".join(parts)) if parts else "none", not parts, notes
    if skill_id == "visual-quality-reviewer":
        return ("automated" + ("+vision" if c("analysis.visionLLM") else "")), False, notes
    if skill_id == "shorts-motion-designer":
        return ("presets" if c("overlay.motionPresets") else "basic-text"), False, notes
    return "default", False, notes


def plan(request: Dict, manifest: Dict, registry: Dict) -> Dict:
    intent = dict(parse_intent(request["instruction"]))
    intent.update(request.get("intent", {}))  # explicit structured intent wins over keywords
    intensity = intent["intensity"]
    skills_out, warnings = [], []
    status_by_id: Dict[str, str] = {}

    for s in sorted(registry["skills"], key=lambda x: x.get("stage", 99)):
        sid = s["id"]
        entry = {"id": sid, "status": "planned", "mode": "", "reasons": []}
        wanted = sid in _ALWAYS or intent.get(_SKILL_INTENT.get(sid, ""), False)
        if not s["enabled"]:
            entry.update(status="skipped", mode="off", reasons=["disabled in skills.registry.json (opt-in)"])
        elif not wanted:
            entry.update(status="skipped", mode="off", reasons=["not requested by the instruction"])
        else:
            req_missing = [k for k in s["requires"] if _cap(manifest, k) != "implemented"]
            documented = [k for k in req_missing if _cap(manifest, k) == "documented"]
            if req_missing:
                entry["missingCapabilities"] = req_missing
                if documented and len(documented) == len(req_missing):
                    entry.update(status="blocked", mode="off",
                                 reasons=["required capability has a recipe but no runtime yet — integrate first"])
                    entry["needsIntegration"] = documented
                else:
                    entry.update(status="skipped", mode="off", reasons=["required capability missing/incompatible"])
            else:
                mode, degraded, notes = _mode(sid, manifest, intent, request)
                if mode in ("none", "off"):
                    entry.update(status="skipped", mode="off", reasons=notes or ["no usable capability"])
                else:
                    entry.update(status="fallback" if degraded else "planned", mode=mode,
                                 reasons=notes or ["requested and supported"])
                rec = [k for k in s["optional"] if _cap(manifest, k) == "documented"]
                if rec:
                    entry["needsIntegration"] = rec
                if degraded and not notes:
                    entry["reasons"] = ["degraded mode — optional capabilities not implemented: "
                                        + ", ".join(rec or ["(see manifest)"])]
        status_by_id[sid] = entry["status"]
        skills_out.append(entry)

    if intent.get("cut") and status_by_id.get("smart-cut-pacing") not in ("planned", "fallback"):
        warnings.append("User asked to cut, but cutting is unavailable — output keeps original timing.")
    if intent.get("vfx") and status_by_id.get("cinematic-vfx") == "skipped":
        warnings.append("VFX requested but the skill is opt-in/disabled; enable it in the registry after Phase 4.")

    active = lambda sid: status_by_id.get(sid) in ("planned", "fallback")  # noqa: E731
    stages: List[Dict] = []

    def add(sid_or_none, sid, action, inputs, outputs, gate=None):
        if sid_or_none is None or active(sid_or_none):
            st = {"order": len(stages) + 1, "id": sid, "skill": sid_or_none, "action": action,
                  "inputs": inputs, "outputs": outputs}
            if gate:
                st["gate"] = gate
            stages.append(st)

    add(None, "probe", "ffprobe source; copy source read-only; create revision folder", ["source"], ["probe"],
        "abort if no video stream or duration <= 0")
    add(None, "transcript", "load transcript; NFC-normalise; mark wordTimestampsReliable", ["source"], ["transcript"])
    add("smart-cut-pacing", "cut", "detect silences/fillers/retakes -> cutList; remap transcript to output time",
        ["probe", "transcript"], ["cutList", "transcript@output"], "removed ratio <= constraints.maxRemovedRatio")
    add("editing-director", "direct", "segment analysis -> per-segment decisions within effect budget",
        ["transcript@output", "cutList"], ["contentAnalysis", "directorDecisions"])
    add("smart-captions", "captions", "chunk -> pages -> style/placement -> caption track (+ASS)",
        ["transcript@output", "directorDecisions"], ["captionTrack"])
    add("camera-movement", "camera", "decisions -> camera keyframes, bounds-checked", ["directorDecisions", "probe"], ["cameraTrack"])
    add("advanced-transitions", "transitions", "classify each cut boundary -> transition plan", ["cutList", "cameraTrack", "directorDecisions"], ["transitionPlan"])
    add("cinematic-vfx", "vfx", "accent VFX within perf budget", ["directorDecisions"], ["vfxPlan"])
    add("audio-director", "audio", "loudness, cut crossfades, optional duck/SFX", ["cutList", "transitionPlan", "captionTrack"], ["audioMixPlan"])
    add("shorts-motion-designer", "compile-overlays", "captionTrack + director accents -> ShortsMotionPlan v1.0", ["captionTrack", "directorDecisions"], ["motionPlan"])
    add(None, "conflict-check", "apply CR-01..CR-10 across all sections; drop lower-priority items", ["*"], ["resolvedSections"])
    add(None, "preview", "render low-res preview (540x960) to new revision path", ["resolvedSections"], ["previewVideo"])
    add("visual-quality-reviewer", "qa", "automated checks + contact sheet -> findings", ["previewVideo", "resolvedSections"], ["qaReport"],
        "no blocker findings")
    add(None, "revise", "route each finding.suggestedFix to its owner skill, bump revision, re-render", ["qaReport"], ["revision+1"])
    add(None, "export", "full-res export to new path; ffprobe verify; write report", ["resolvedSections"], ["finalVideo", "report"],
        "requireApprovalBeforeExport -> wait for user")

    cons = request.get("constraints", {})
    return {
        "planVersion": "1.0",
        "instruction": request["instruction"],
        "resolvedIntent": intent,
        "intensity": intensity,
        "effectBudget": BUDGETS[intensity],
        "skills": skills_out,
        "stages": stages,
        "conflictRules": [f"CR-{i:02d}" for i in range(1, 11)],
        "reviewLoop": {"maxIterations": cons.get("maxReviewIterations", 2),
                       "stopWhen": "no blocker and no major findings, or maxIterations reached (then report remaining findings)"},
        "rollback": {"neverOverwrite": True, "keepRevisions": 5, "allSkillsOffEqualsBaseline": True},
        "warnings": warnings,
    }


def main(argv: List[str]) -> int:
    req, man, reg = (load_json(p) for p in argv[1:4])
    here = Path(__file__).resolve().parents[1]
    for obj, schema in ((req, here / "schemas/edit-request.schema.json"),
                        (man, ROOT / "core/schemas/capability-manifest.schema.json"),
                        (reg, ROOT / "core/schemas/skill-registry.schema.json")):
        errs = validate(obj, load_json(schema))
        if errs:
            print("INPUT INVALID:\n" + "\n".join(errs), file=sys.stderr)
            return 2
    out = plan(req, man, reg)
    errs = validate(out, load_json(here / "schemas/orchestration-plan.schema.json"))
    if errs:
        print("PLAN INVALID:\n" + "\n".join(errs), file=sys.stderr)
        return 3
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv))
