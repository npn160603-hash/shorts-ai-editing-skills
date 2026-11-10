"""Long video -> several Shorts: find self-contained highlight windows in a transcript (no AI needed).

Windows start at a sentence start and end at a sentence end, last `minSec..maxSec`, and are scored
with measurable signals (Skill 01 lexicon): hook strength of the first sentence (question, number,
emphasis words, direct address), keyword density, list/proof/climax markers, comfortable speech rate,
few long pauses, not just a CTA. An optional LLM may add a bounded bonus per window (see sae_llm).
"""
from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

import director as D
from sae_text import ends_sentence, tokenize_words

HOOK_ADDRESS = r"\b(ban|cac ban|minh|toi|you|your)\b"


def _sentences(transcript: Dict) -> List[Dict]:
    """Merge transcript segments into sentences (segments may already be sentences)."""
    out, cur = [], None
    for s in transcript["segments"]:
        if cur is None:
            cur = dict(s)
        else:
            cur["text"] = f"{cur['text']} {s['text']}"
            cur["endSec"] = s["endSec"]
        if ends_sentence(s["text"].strip()) or s is transcript["segments"][-1]:
            out.append(cur)
            cur = None
    return out


def _score_window(sents: List[Dict], words: List[Dict]) -> Dict:
    a, b = sents[0]["startSec"], sents[-1]["endSec"]
    dur = b - a
    first = sents[0]["text"]
    f_first = D.fold(first)
    text = " ".join(s["text"] for s in sents)
    reasons, sc = [], 0.0
    if first.strip().endswith("?"):
        sc += 1.2
        reasons.append("mở bằng câu hỏi")
    if re.search(r"\d", first):
        sc += 0.9
        reasons.append("mở bằng con số")
    if re.search(D.LEX["emphasis"], f_first):
        sc += 0.8
        reasons.append("mở bằng từ nhấn mạnh")
    if re.search(HOOK_ADDRESS, f_first):
        sc += 0.4
        reasons.append("nói thẳng với người xem")
    if sc == 0.0:
        sc -= 0.6
        reasons.append("câu mở đầu yếu (không câu hỏi/số/nhấn mạnh)")
    kws = sum(len(D.keyword_candidates(s["text"])) for s in sents)
    dens = kws / max(dur, 1.0) * 10
    sc += min(dens, 3.0) * 0.5
    if kws:
        reasons.append(f"{kws} từ khoá")
    ft = D.fold(text)
    for key, w, label in (("point", 0.6, "có ý liệt kê/mẹo"), ("proof", 0.5, "có dẫn chứng"), ("emphasis", 0.4, "có nhấn mạnh")):
        if re.search(D.LEX[key], ft):
            sc += w
            reasons.append(label)
    ws = [w for w in words if a - 1e-3 <= w["startSec"] < b]
    n_words = len(ws) or len(tokenize_words(text))
    rate = n_words / max(dur, 1e-6)
    if 2.0 <= rate <= 4.0:
        sc += 0.6
    else:
        sc -= 0.6
        reasons.append(f"tốc độ nói {rate:.1f} từ/s (lệch)")
    gaps = [y["startSec"] - x["endSec"] for x, y in zip(ws, ws[1:])]
    long_gaps = sum(1 for g in gaps if g > 1.5)
    if long_gaps:
        sc -= 0.4 * long_gaps
        reasons.append(f"{long_gaps} khoảng lặng dài")
    if len(sents) <= 2 and re.search(D.LEX["cta"], ft):
        sc -= 2.0
        reasons.append("chủ yếu là lời kêu gọi")
    if not ends_sentence(sents[-1]["text"].strip()):
        sc -= 0.8
        reasons.append("kết thúc giữa câu")
    return {"startSec": round(a, 3), "endSec": round(b, 3), "durationSec": round(dur, 2), "score": round(sc, 3),
            "reasons": reasons, "firstSentence": first.strip(), "keywords": D.keyword_candidates(text, 4)}


def find_highlights(transcript: Dict, count: int = 5, min_sec: float = 20.0, max_sec: float = 60.0,
                    min_gap: float = 2.0, bonus: Optional[Callable[[Dict], float]] = None) -> Dict:
    sents = _sentences(transcript)
    words = transcript.get("words", [])
    cands = []
    for i in range(len(sents)):
        for j in range(i, len(sents)):
            dur = sents[j]["endSec"] - sents[i]["startSec"]
            if dur > max_sec:
                break
            if dur >= min_sec:
                c = _score_window(sents[i:j + 1], words)
                if bonus:
                    extra = max(-1.0, min(1.0, float(bonus(c))))  # bounded: AI can nudge, not dominate
                    if extra:
                        c["score"] = round(c["score"] + extra, 3)
                        c["reasons"].append(f"LLM {extra:+.1f}")
                cands.append(c)
    cands.sort(key=lambda c: (-c["score"], c["startSec"]))
    chosen: List[Dict] = []
    for c in cands:
        if len(chosen) >= count:
            break
        if all(c["endSec"] + min_gap <= x["startSec"] or c["startSec"] >= x["endSec"] + min_gap for x in chosen):
            chosen.append(c)
    chosen.sort(key=lambda c: c["startSec"])
    for k, c in enumerate(chosen, 1):
        c["id"] = f"clip-{k:02d}"
    return {"highlightsVersion": "1.0", "timebase": "source", "count": len(chosen),
            "params": {"minSec": min_sec, "maxSec": max_sec, "requested": count}, "clips": chosen,
            "candidatesConsidered": len(cands)}


def slice_transcript(transcript: Dict, a: float, b: float, offset: Optional[float] = None) -> Dict:
    """Clip-local transcript (time 0 = `offset`, default a). Words/segments outside [a, b) are
    dropped, never invented. Use offset = the excerpt's real start (a - pad) when extracting."""
    o = a if offset is None else offset
    segs = []
    for s in transcript["segments"]:
        if s["startSec"] >= a - 1e-3 and s["endSec"] <= b + 1e-3:
            segs.append(dict(s, startSec=round(s["startSec"] - o, 3), endSec=round(s["endSec"] - o, 3)))
    words = [dict(w, startSec=round(w["startSec"] - o, 3), endSec=round(w["endSec"] - o, 3))
             for w in transcript.get("words", []) if w["startSec"] >= a - 1e-3 and w["endSec"] <= b + 1e-3]
    out = dict(transcript, segments=segs, timebase="source")
    if transcript.get("words") is not None:
        out["words"] = words
    return out


def extract_cmd(src: str, a: float, b: float, dst: str, pad: float = 0.15) -> List[str]:
    """Frame-accurate re-encoded excerpt (keeps the original untouched; refuses to overwrite)."""
    s = max(0.0, a - pad)
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-ss", f"{s:.3f}", "-i", src, "-t", f"{(b - s) + pad:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", dst]
