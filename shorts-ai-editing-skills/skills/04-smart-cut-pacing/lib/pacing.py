"""Skill 04 — Smart Cut & Pacing reference implementation (stdlib only).

Method labels used in the cut list (see references/methods-signal-heuristic-ai.md):
  signal    = measured from audio/video (ffmpeg silencedetect, scene score)
  heuristic = rule on transcript text/timing (fillers, retakes, word gaps)
  ai        = needs a model (semantic redundancy) — never produced here, only accepted as input
"""
from __future__ import annotations

import difflib
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "lib"))
from sae_timeline import EPS, invert_ranges, merge_ranges, snap  # noqa: E402

PRESETS = {
    #            remove pauses longer than | keep this much pause on each side | head/tail pad
    "subtle":  {"minSilenceSec": 0.70, "keepPauseSec": 0.22, "edgePadSec": 0.25, "minKeepSec": 0.30},
    "normal":  {"minSilenceSec": 0.45, "keepPauseSec": 0.14, "edgePadSec": 0.15, "minKeepSec": 0.25},
    "dynamic": {"minSilenceSec": 0.28, "keepPauseSec": 0.08, "edgePadSec": 0.10, "minKeepSec": 0.20},
}

FILLERS = {
    "vi": {"ừm", "ừ", "ờ", "ơ", "à", "ạ", "hừm", "ừmm", "ờm", "uhm", "um"},
    "en": {"um", "uh", "uhm", "erm", "er", "hmm", "mm"},
}

_SIL_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SIL_END = re.compile(r"silence_end:\s*([\d.]+)")
_PTS = re.compile(r"pts_time:([\d.]+)")


# ---------------------------------------------------------------- signal parsing
def parse_silencedetect(log: str, duration: float) -> List[Tuple[float, float]]:
    """Parse stderr of: ffmpeg -i in -af silencedetect=noise=-35dB:d=0.25 -f null -"""
    out, start = [], None
    for line in log.splitlines():
        m = _SIL_START.search(line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = _SIL_END.search(line)
        if m and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    if start is not None:
        out.append((start, duration))
    return out


def parse_scene_changes(log: str) -> List[float]:
    """Parse stderr of: ffmpeg -i in -vf "select='gt(scene,0.35)',showinfo" -f null -"""
    return [float(m.group(1)) for line in log.splitlines() if "showinfo" in line
            for m in [_PTS.search(line)] if m]


def word_gaps(words: Sequence[Dict], duration: float) -> List[Tuple[float, float]]:
    """Pauses between words (heuristic silence source when no audio analysis exists)."""
    gaps, cur = [], 0.0
    for w in sorted(words, key=lambda x: x["startSec"]):
        if w["startSec"] > cur + EPS:
            gaps.append((cur, w["startSec"]))
        cur = max(cur, w["endSec"])
    if duration > cur + EPS:
        gaps.append((cur, duration))
    return gaps


# ---------------------------------------------------------------- text heuristics
def _fold(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower())
    return re.sub(r"[^\w\s]", "", s).strip()


def find_fillers(words: Sequence[Dict], language: str) -> List[Dict]:
    """Standalone filler tokens. Only single tokens from a closed list are removed —
    multi-word discourse markers ("kiểu như") are reported but NOT cut automatically."""
    lex = FILLERS.get(language.split("-")[0], set())
    out = []
    for w in words:
        if _fold(w["text"]) in lex:
            out.append({"srcStartSec": w["startSec"], "srcEndSec": w["endSec"], "reason": "filler",
                        "method": "heuristic", "confidence": round(0.9 if w.get("confidence", 1) < 0.8 else 0.75, 2),
                        "note": f"filler token '{w['text']}'"})
    return out


def find_retakes(segments: Sequence[Dict], threshold: float = 0.72) -> List[Dict]:
    """Consecutive segments whose openings are near-identical -> earlier one is a retake.
    Heuristic: compares the first 6 folded words. Always low confidence -> review in QA."""
    out = []
    for a, b in zip(segments, segments[1:]):
        wa, wb = _fold(a["text"]).split()[:6], _fold(b["text"]).split()[:6]
        if len(wa) >= 3 and difflib.SequenceMatcher(None, wa, wb).ratio() >= threshold:
            out.append({"srcStartSec": a["startSec"], "srcEndSec": b["startSec"], "reason": "retake",
                        "method": "heuristic", "confidence": 0.6,
                        "note": f"segment {a['id']} repeats opening of {b['id']}"})
    return out


# ---------------------------------------------------------------- cut list
def silence_removals(silences: Sequence[Tuple[float, float]], duration: float, p: Dict, method: str) -> List[Dict]:
    out = []
    for a, b in silences:
        is_head, is_tail = a <= EPS, b >= duration - EPS
        if b - a < p["minSilenceSec"] and not (is_head or is_tail):
            continue
        ra = a if is_head else a + p["keepPauseSec"]
        rb = b if is_tail else b - p["keepPauseSec"]
        if is_head:
            rb = max(0.0, b - p["edgePadSec"])
        if is_tail:
            ra = min(duration, a + p["edgePadSec"])
        if rb - ra > EPS:
            out.append({"srcStartSec": ra, "srcEndSec": rb,
                        "reason": "head" if is_head else "tail" if is_tail else "silence",
                        "method": method, "confidence": 0.95 if method == "signal" else 0.85})
    return out


def build_cut_list(duration: float, fps: float, removals: List[Dict], intensity: str = "normal",
                   max_removed_ratio: float = 0.35, protected: Sequence[Tuple[float, float]] = (),
                   speech: Sequence[Tuple[float, float]] = (), overrides: Optional[Dict] = None) -> Dict:
    """Combine candidate removals into keep segments.

    - `protected` ranges (e.g. words the director marked as essential) are never cut.
    - If total removal exceeds max_removed_ratio, lowest-confidence/shortest removals are
      dropped first (reported in `rejected`).
    - A kept sliver shorter than minKeepSec between two removals is cut too when it holds
      no speech (from `speech` ranges); if it holds speech it is kept and merged backwards.
    """
    p = dict(PRESETS[intensity], **(overrides or {}))
    cands = []
    for r in removals:
        a, b = snap(r["srcStartSec"], fps), snap(r["srcEndSec"], fps)
        if any(a < pb and pa < b for pa, pb in protected):
            continue
        if b - a >= 1.0 / fps - EPS:
            cands.append(dict(r, srcStartSec=a, srcEndSec=b))
    cands.sort(key=lambda r: (-r["confidence"], -(r["srcEndSec"] - r["srcStartSec"])))
    accepted, rejected, budget = [], [], max_removed_ratio * duration
    used = 0.0
    for r in cands:
        merged = merge_ranges([(x["srcStartSec"], x["srcEndSec"]) for x in accepted + [r]])
        total = sum(b - a for a, b in merged)
        if total <= budget + EPS:
            accepted.append(r)
            used = total
        else:
            rejected.append(dict(r, note=(r.get("note", "") + " | rejected: maxRemovedRatio").strip(" |")))
    keeps = invert_ranges([(r["srcStartSec"], r["srcEndSec"]) for r in accepted], duration)
    # drop keep slivers shorter than minKeepSec by un-cutting around them (merge with neighbours)
    keeps = [(snap(a, fps), snap(b, fps)) for a, b in keeps]
    filtered = []
    for a, b in keeps:
        if b - a < p["minKeepSec"]:
            has_speech = any(a < sb - EPS and sa < b - EPS for sa, sb in speech)
            if not has_speech and 0 < a and b < duration:
                continue  # silent sliver between two cuts: cut it as well
            if filtered:
                filtered[-1] = (filtered[-1][0], b)  # speech sliver: un-cut, merge with previous keep
                continue
        filtered.append((a, b))
    keeps = filtered
    segs, cursor = [], 0.0
    for i, (a, b) in enumerate(keeps):
        segs.append({"id": f"k{i + 1:03d}", "srcStartSec": round(a, 4), "srcEndSec": round(b, 4),
                     "outStartSec": round(cursor, 4)})
        cursor += b - a
    removed_ranges = invert_ranges(keeps, duration)
    removed_sec = sum(b - a for a, b in removed_ranges)
    for r in accepted:
        r["srcStartSec"], r["srcEndSec"] = round(r["srcStartSec"], 4), round(r["srcEndSec"], 4)
    accepted.sort(key=lambda r: r["srcStartSec"])
    return {
        "cutListVersion": "1.0",
        "timebase": "source",
        "sourceDurationSec": round(duration, 4),
        "fps": fps,
        "intensity": intensity,
        "params": dict(p, maxRemovedRatio=max_removed_ratio),
        "segments": segs,
        "removed": accepted,
        "rejected": rejected,
        "stats": {"removedSec": round(removed_sec, 3), "removedRatio": round(removed_sec / duration, 4),
                  "outputDurationSec": round(cursor, 4), "cutCount": max(0, len(segs) - 1)},
    }


def pacing_metrics(words: Sequence[Dict], segments: Sequence[Dict]) -> List[Dict]:
    """Words-per-second per transcript segment (speech-aware timing input for Skill 01)."""
    out = []
    for s in segments:
        ws = [w for w in words if w.get("segmentId") == s["id"]] or \
             [w for w in words if s["startSec"] - EPS <= w["startSec"] < s["endSec"]]
        dur = max(s["endSec"] - s["startSec"], EPS)
        out.append({"segmentId": s["id"], "wordsPerSec": round(len(ws) / dur, 2), "durationSec": round(dur, 3)})
    return out


# ---------------------------------------------------------------- render recipe
def ffmpeg_concat_filter(cut_list: Dict, audio_fade_ms: float = 10.0, has_audio: bool = True) -> str:
    """trim/atrim + concat filter_complex. Video trims are FRAME-exact (start_frame/end_frame;
    source must be CFR — normalise VFR first). Audio uses the same frame boundaries in seconds,
    with a short fade in/out per piece so jump cuts do not click (CR-06). Labels: [vout][aout]."""
    fps = cut_list["fps"]
    f = audio_fade_ms / 1000.0
    parts, labels = [], []
    for i, s in enumerate(cut_list["segments"]):
        n0, n1 = int(round(s["srcStartSec"] * fps)), int(round(s["srcEndSec"] * fps))
        a, b = n0 / fps, n1 / fps
        parts.append(f"[0:v]trim=start_frame={n0}:end_frame={n1},setpts=PTS-STARTPTS[v{i}]")
        lab = f"[v{i}]"
        if has_audio:
            parts.append(f"[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:st=0:d={f:.3f},afade=t=out:st={max(0.0, b - a - f):.6f}:d={f:.3f}[a{i}]")
            lab += f"[a{i}]"
        labels.append(lab)
    n = len(labels)
    parts.append("".join(labels) + f"concat=n={n}:v=1:a={1 if has_audio else 0}[vout]" + ("[aout]" if has_audio else ""))
    return ";".join(parts)


def plan_cuts(transcript: Dict, duration: float, fps: float, intensity: str = "normal",
              max_removed_ratio: float = 0.35, silence_log: Optional[str] = None,
              semantic_removals: Sequence[Dict] = (), overrides: Optional[Dict] = None,
              protected: Sequence[Tuple[float, float]] = ()) -> Dict:
    """End-to-end: signal silences if a log is given, else word gaps; + fillers + retakes
    + externally supplied AI/semantic removals (must carry method='ai')."""
    p = dict(PRESETS[intensity], **(overrides or {}))
    words = transcript.get("words", [])
    if silence_log is not None:
        sil, method = parse_silencedetect(silence_log, duration), "signal"
    elif words and transcript.get("wordTimestampsReliable"):
        sil, method = word_gaps(words, duration), "heuristic"
    else:
        sil, method = [], "heuristic"
    removals = silence_removals(sil, duration, p, method)
    if words and transcript.get("wordTimestampsReliable"):
        removals += find_fillers(words, transcript["language"])
    removals += find_retakes(transcript["segments"])
    for r in semantic_removals:
        if r.get("method") != "ai":
            raise ValueError("semantic removals must be labelled method='ai'")
        removals.append(dict(r))
    speech = [(w["startSec"], w["endSec"]) for w in words] or \
             [(x["startSec"], x["endSec"]) for x in transcript["segments"]]
    return build_cut_list(duration, fps, removals, intensity, max_removed_ratio, protected=protected,
                          speech=speech, overrides=overrides)


def remap_transcript(transcript: Dict, cut_list: Dict) -> Dict:
    """Source-time transcript -> output-time transcript. Removed words disappear; segment
    text is rebuilt from surviving words (so captions never show a cut filler)."""
    from sae_timeline import keep_map_from_cutlist, remap_range, remap_words
    segs = keep_map_from_cutlist(cut_list)
    words = remap_words(transcript.get("words", []), segs)
    out_segments = []
    for s in transcript["segments"]:
        r = remap_range(s["startSec"], s["endSec"], segs)
        if r is None:
            continue
        ns = dict(s, startSec=round(r[0], 4), endSec=round(r[1], 4))
        sw = [w for w in words if w.get("segmentId") == s["id"]]
        if sw:
            ns["text"] = " ".join(w["text"] for w in sw)
            ns["startSec"], ns["endSec"] = sw[0]["startSec"], max(w["endSec"] for w in sw)
        out_segments.append(ns)
    return dict(transcript, timebase="output", segments=out_segments, words=words)
