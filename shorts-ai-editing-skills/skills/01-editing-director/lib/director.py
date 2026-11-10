"""Skill 01 — AI Video Editing Director: heuristic rule engine (stdlib only).

analyze()  : output-time transcript (+ optional signals) -> ContentAnalysis
decide()   : ContentAnalysis + intensity/budget + cut boundaries -> DirectorDecisions

Optional AI hook: an LLM may supply `role`, `importance`, `keywords`, `sincere` per segment
(roleSource="ai"). The rule engine treats them as inputs; budgets and restraint rules still apply.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "lib"))
from sae_text import is_number_like, nfc, strip_punct, tokenize_words  # noqa: E402

BUDGETS = {  # mirrors orchestrator BUDGETS; the orchestrator's value wins when provided
    "subtle":  {"maxAccentsPer10s": 1.5, "minGapBetweenAccentsSec": 2.5, "maxCameraMovesPer10s": 1.0},
    "normal":  {"maxAccentsPer10s": 2.5, "minGapBetweenAccentsSec": 1.6, "maxCameraMovesPer10s": 2.0},
    "dynamic": {"maxAccentsPer10s": 4.0, "minGapBetweenAccentsSec": 1.0, "maxCameraMovesPer10s": 3.5},
}
PUNCH_LEVELS = {"subtle": 1.06, "normal": 1.12, "dynamic": 1.18}

LEXICON_FILE = Path(__file__).resolve().parents[1] / "references" / "lexicon.json"


def load_lexicon(path: Optional[Path] = None) -> Dict[str, str]:
    """Compile references/lexicon.json (editable per channel) into whole-word regexes."""
    import json as _json
    data = _json.loads(Path(path or LEXICON_FILE).read_text(encoding="utf-8"))
    out = {}
    for key in ("cta", "proof", "point", "sincere", "emphasis"):
        phrases = sorted({p.strip().lower() for p in data.get(key, []) if p.strip()}, key=len, reverse=True)
        out[key] = r"\b(" + "|".join(re.escape(p).replace("\\ ", r"\s+") for p in phrases) + r")\b" if phrases else r"(?!x)x"
    return out


LEX = load_lexicon()
STOP = set("la va cua cho voi nhung cac mot nhieu thi ma de khi nay do the nao ban toi minh chung ta co khong duoc "
           "the a an and or but to of in on is are be it this that you i we".split())


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", nfc(s).lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _has(pat_key: str, text: str) -> bool:
    return bool(re.search(LEX[pat_key], fold(text)))


def keyword_candidates(text: str, max_n: int = 3) -> List[str]:
    """Numbers (+ following unit word), emphasis lexicon hits, ALL-CAPS words; never invented."""
    words = tokenize_words(text)
    out: List[str] = []
    for i, w in enumerate(words):
        core = strip_punct(w)
        if not core:
            continue
        if is_number_like(core):
            unit = strip_punct(words[i + 1]) if i + 1 < len(words) else ""
            out.append(f"{core} {unit}".strip() if unit and not is_number_like(unit) else core)
        elif re.search(LEX["emphasis"], fold(core)):
            out.append(core)
        elif core.isupper() and len(core) > 1:
            out.append(core)
    # two-word emphasis phrases ("lãng phí", "khác biệt")
    for a, b in zip(words, words[1:]):
        pair = f"{strip_punct(a)} {strip_punct(b)}"
        if re.search(LEX["emphasis"], fold(pair)) and not re.search(LEX["emphasis"], fold(strip_punct(a))) \
                and not re.search(LEX["emphasis"], fold(strip_punct(b))):
            out.append(pair)
    # list markers: "Mẹo số một", "Bước 2", "Tip 3" -> keep the marker phrase
    for i, w in enumerate(words):
        if fold(strip_punct(w)) in ("meo", "buoc", "tip", "step", "cach"):
            span = [strip_punct(x) for x in words[i:i + 3]]
            if len(span) >= 2 and fold(span[1]) == "so" and len(span) == 3:
                out.insert(0, " ".join(span))
            elif len(span) >= 2 and (is_number_like(span[1]) or fold(span[1]) in ("mot", "hai", "ba", "one", "two", "three")):
                out.insert(0, " ".join(span[:2]))
            break
    seen, uniq = set(), []
    for k in out:
        if fold(k) not in seen:
            seen.add(fold(k))
            uniq.append(k)
    return uniq[:max_n]


def analyze(transcript: Dict, duration: float, scene_changes: Sequence[float] = (),
            ai_overrides: Optional[Dict[str, Dict]] = None) -> Dict:
    if transcript["timebase"] != "output":
        raise ValueError("Director works on output time — run Skill 04 remap first (identity if no cuts).")
    ai_overrides = ai_overrides or {}
    segs = transcript["segments"]
    out = []
    hook_end = 0.0
    for idx, s in enumerate(segs):
        text = s["text"]
        dur = max(s["endSec"] - s["startSec"], 1e-6)
        n_words = len(tokenize_words(text))
        feats = {
            "wordsPerSec": round(n_words / dur, 2),
            "isQuestion": text.strip().endswith("?"),
            "hasNumber": any(is_number_like(w) for w in tokenize_words(text)),
            "hasEmphasisWord": _has("emphasis", text),
            "sincere": _has("sincere", text),
            "sceneChangeNear": any(abs(t - s["startSec"]) < 0.3 for t in scene_changes),
        }
        if idx == 0 or s["startSec"] < 1.5:
            role = "hook"
            hook_end = max(hook_end, s["endSec"])
        elif idx == len(segs) - 1 and _has("cta", text):
            role = "cta"
        elif _has("point", text):
            role = "point"
        elif _has("proof", text) or feats["hasNumber"]:
            role = "proof"
        else:
            role = "setup"
        imp = 0.15 + 0.3 * feats["hasNumber"] + 0.2 * feats["isQuestion"] + 0.25 * feats["hasEmphasisWord"] \
            + {"hook": 0.25, "point": 0.15, "proof": 0.1, "cta": 0.0, "setup": 0.0}[role]
        entry = {"id": s["id"], "startSec": s["startSec"], "endSec": s["endSec"], "text": text,
                 "role": role, "roleSource": "heuristic", "importance": round(min(imp, 1.0), 2),
                 "keywords": keyword_candidates(text), "features": feats}
        ov = ai_overrides.get(s["id"])
        if ov:
            # AI output is data, not truth: keywords must literally occur in the segment text
            ov = dict(ov)
            ov["keywords"] = [k for k in ov.get("keywords", entry["keywords"]) if fold(k) in fold(text)][:5]
            if ov.get("role") not in ("hook", "setup", "point", "proof", "climax", "payoff", "cta"):
                ov.pop("role", None)
            if "importance" in ov:
                ov["importance"] = max(0.0, min(1.0, float(ov["importance"])))
            entry.update({k: v for k, v in ov.items() if k in ("role", "importance", "keywords")})
            if "sincere" in ov:
                entry["features"]["sincere"] = bool(ov["sincere"])
            entry["roleSource"] = "ai"
        out.append(entry)
    # the most important non-hook, non-cta segment in the last 60% becomes the climax
    tail = [e for e in out if e["role"] not in ("hook", "cta") and e["startSec"] >= 0.4 * duration]
    if tail:
        max(tail, key=lambda e: e["importance"])["role"] = "climax"
    return {"analysisVersion": "1.0", "timebase": "output", "durationSec": round(duration, 4),
            "hookEndSec": round(min(max(hook_end, 1.0), 3.0), 3), "segments": out}


def _word_time(words: Sequence[Dict], seg: Dict, keyword: str) -> Optional[float]:
    first = fold(strip_punct(keyword.split()[0]))
    for w in words:
        if seg["startSec"] - 1e-3 <= w["startSec"] < seg["endSec"] and fold(strip_punct(w["text"])) == first:
            return w["startSec"]
    return None


def decide(analysis: Dict, intensity: str = "normal", budget: Optional[Dict] = None,
           cut_points_out: Sequence[float] = (), words: Sequence[Dict] = (),
           allow_camera: bool = True) -> Dict:
    b = dict(BUDGETS[intensity], **(budget or {}))
    punch = PUNCH_LEVELS[intensity]
    cands: List[Dict] = []
    decisions = []
    for seg in analysis["segments"]:
        f = seg["features"]
        d = {"segmentId": seg["id"], "startSec": seg["startSec"], "endSec": seg["endSec"], "role": seg["role"],
             "pacing": "normal", "protectAfterSec": 0.0, "captionMode": "standard", "restraint": []}
        if f["sincere"]:
            d["restraint"].append("sincere-moment: no accents, no camera moves")
            d["pacing"] = "hold"
            d["captionMode"] = "calm"
        if f["wordsPerSec"] > 3.6:
            d["restraint"].append("dense-speech: max 1 accent, no extra pause cutting")
            d["pacing"] = "hold"
        if f["isQuestion"] or seg["role"] == "climax":
            d["protectAfterSec"] = 0.35
        if seg["role"] == "hook":
            d["pacing"] = "tighten"
            d["captionMode"] = "headline"
        if seg["role"] == "cta":
            d["restraint"].append("cta: keep frame calm, caption-only")
            d["captionMode"] = "cta"
        decisions.append(d)
        if f["sincere"] or seg["role"] == "cta":
            continue
        dense = f["wordsPerSec"] > 3.6
        for k_i, kw in enumerate(seg["keywords"][: (1 if dense else 2)]):
            t = _word_time(words, seg, kw) if words else None
            at = t if t is not None else seg["startSec"] + 0.15
            score = seg["importance"] + (0.15 if is_number_like(kw) else 0) - 0.1 * k_i
            cands.append({"type": "keyword-pop", "atSec": round(at, 3), "durationSec": 0.6, "target": kw,
                          "segmentId": seg["id"], "score": round(score, 3), "timing": "word" if t is not None else "segment",
                          "reason": f"keyword in {seg['role']} segment"})
        if allow_camera and seg["role"] in ("climax", "point") and not dense:
            cands.append({"type": "punch-in", "atSec": round(seg["startSec"], 3), "durationSec": round(seg["endSec"] - seg["startSec"], 3),
                          "zoom": punch, "segmentId": seg["id"], "score": round(seg["importance"] + 0.05, 3),
                          "reason": f"{seg['role']} emphasis"})
        if seg["role"] == "proof" and f["hasNumber"] and seg["endSec"] - seg["startSec"] >= 2.0:
            cands.append({"type": "callout", "atSec": round(seg["startSec"] + 0.2, 3), "durationSec": 1.8,
                          "target": (seg["keywords"] or [""])[0], "segmentId": seg["id"],
                          "score": round(seg["importance"], 3), "reason": "number worth a card"})
    hook_end = analysis["hookEndSec"]
    if allow_camera and analysis["segments"]:
        cands.append({"type": "smooth-push", "atSec": 0.0, "durationSec": round(hook_end, 3), "zoom": round(1 + (punch - 1) * 0.6, 3),
                      "segmentId": analysis["segments"][0]["id"], "score": 0.99, "reason": "hook: slow push-in draws the eye"})
    # jump-cut cover: alternate zoom at each cut (camera budget only, not an accent)
    jump_moves = []
    if allow_camera:
        level = 1.0
        for t in sorted(cut_points_out):
            if t < hook_end:
                continue
            level = punch if level == 1.0 else 1.0
            jump_moves.append({"type": "jump-cut-reframe", "atSec": round(t, 3), "durationSec": 0.0, "zoom": level,
                               "score": 0.5, "reason": "alternate framing hides the jump cut"})

    accepted: List[Dict] = []
    dropped: List[Dict] = []
    is_cam = lambda a: a["type"] in ("punch-in", "smooth-push", "jump-cut-reframe")  # noqa: E731
    is_text = lambda a: a["type"] in ("keyword-pop", "callout", "headline", "vfx-accent")  # noqa: E731

    def over_budget(c: Dict, pred, limit: float) -> bool:
        """True if adding c makes ANY rolling 10 s window (centred on c or on an accepted
        accent of the same channel) exceed `limit` — the same rule QA (Skill 08) checks."""
        items = [a for a in accepted if pred(a)] + [c]
        for centre in items:
            if abs(centre["atSec"] - c["atSec"]) >= 5.0:
                continue
            if sum(1 for a in items if abs(a["atSec"] - centre["atSec"]) < 5.0) > limit:
                return True
        return False

    # Two channels: overlay accents (text/vfx) and camera. Min gap applies within a channel;
    # a camera accent + a text accent in the same segment form one "paired" accent (CR-05).
    for c in sorted(cands, key=lambda a: -a["score"]) + jump_moves:
        if is_text(c):
            near = [a for a in accepted if is_text(a) and abs(a["atSec"] - c["atSec"]) < b["minGapBetweenAccentsSec"]]
            if near:
                dropped.append(dict(c, droppedBecause="min gap (overlay channel)"))
                continue
            if over_budget(c, is_text, b["maxAccentsPer10s"]):
                dropped.append(dict(c, droppedBecause="accent budget"))
                continue
        if is_cam(c):
            overlap = [a for a in accepted if is_cam(a) and a["atSec"] <= c["atSec"] < a["atSec"] + max(a["durationSec"], 0.001)]
            if overlap or over_budget(c, is_cam, b["maxCameraMovesPer10s"]):
                dropped.append(dict(c, droppedBecause="camera budget/overlap (CR-01)"))
                continue
        accepted.append(c)
    accepted.sort(key=lambda a: a["atSec"])
    return {"decisionsVersion": "1.0", "timebase": "output", "intensity": intensity, "hookEndSec": hook_end,
            "effectBudget": b, "segments": decisions, "accents": accepted, "dropped": dropped}
