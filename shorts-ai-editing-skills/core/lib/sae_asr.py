"""Convert ASR outputs to the shared Transcript format (core/schemas/transcript.schema.json).

Supported inputs (auto-detected by `load_any`):
  - openai-whisper / faster-whisper JSON: {"segments":[{"start","end","text","words":[{"word","start","end","probability"}]}]}
    (faster-whisper: dump `[s._asdict() ...]` or the same structure; a bare list of segments is accepted)
  - whisper.cpp JSON (-oj / -ojf): {"transcription":[{"offsets":{"from","to"} (ms),"text", "tokens":[...]}]}
  - WhisperX JSON: {"segments":[...], "word_segments":[{"word","start","end","score"}]}
  - SRT / WebVTT: phrase-level only (wordTimestampsReliable = false, always).
  - This package's own Transcript JSON (re-checked; reliability can only be downgraded).

`wordTimestampsReliable` is set true ONLY when word timings exist AND pass sanity checks
(monotonic, plausible durations, cover the segments). The reasons are returned so the editor
can show them. Never fabricates word timings for SRT/VTT.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def _seg(i: int, text: str, a: float, b: float) -> Dict:
    return {"id": f"s{i + 1}", "text": _nfc(text), "startSec": round(max(0.0, a), 3), "endSec": round(max(a + 0.01, b), 3)}


def _word(text: str, a: float, b: float, conf: Optional[float], sid: str) -> Optional[Dict]:
    t = _nfc(text)
    if not t or a is None or b is None:
        return None
    w = {"text": t, "startSec": round(float(a), 3), "endSec": round(max(float(a) + 0.01, float(b)), 3), "segmentId": sid}
    if conf is not None:
        w["confidence"] = round(max(0.0, min(1.0, float(conf))), 3)
    return w


def sanity_check_words(words: List[Dict], segments: List[Dict]) -> Tuple[bool, List[str]]:
    reasons = []
    if not words:
        return False, ["no word timings"]
    prev = -1.0
    back = 0
    for w in words:
        if w["startSec"] < prev - 0.05:
            back += 1
        prev = w["startSec"]
    if back:
        reasons.append(f"{back} words go backwards in time")
    durs = [w["endSec"] - w["startSec"] for w in words]
    too_long = sum(1 for d in durs if d > 3.0)
    zero = sum(1 for d in durs if d < 0.02)
    if too_long > 0.02 * len(words):
        reasons.append(f"{too_long} words longer than 3 s (aligner drift?)")
    if zero > 0.1 * len(words):
        reasons.append(f"{zero} words shorter than 20 ms")
    seg_words = sum(len(s["text"].split()) for s in segments)
    if seg_words and abs(len(words) - seg_words) > 0.15 * seg_words:
        reasons.append(f"word count {len(words)} differs from segment text ({seg_words}) by > 15%")
    low = [w for w in words if w.get("confidence", 1.0) < 0.3]
    if len(low) > 0.25 * len(words):
        reasons.append(f"{len(low)} words with confidence < 0.3")
    return not reasons, reasons


def from_whisper(data, language: str, producer: str = "whisper") -> Dict:
    segs_in = data if isinstance(data, list) else data.get("segments", [])
    segments, words = [], []
    for i, s in enumerate(segs_in):
        seg = _seg(i, s.get("text", ""), float(s["start"]), float(s["end"]))
        if not seg["text"]:
            continue
        segments.append(seg)
        for w in s.get("words") or []:
            ww = _word(w.get("word", w.get("text", "")), w.get("start"), w.get("end"),
                       w.get("probability", w.get("score")), seg["id"])
            if ww:
                words.append(ww)
    if not words and isinstance(data, dict) and data.get("word_segments"):  # WhisperX top-level words
        for w in data["word_segments"]:
            sid = next((s["id"] for s in segments if s["startSec"] - 0.05 <= (w.get("start") or -1) < s["endSec"] + 0.05), segments[0]["id"] if segments else "s1")
            ww = _word(w.get("word", ""), w.get("start"), w.get("end"), w.get("score"), sid)
            if ww:
                words.append(ww)
        producer = "whisperx"
    return _finish(language, producer, segments, words)


def from_whisper_cpp(data: Dict, language: str) -> Dict:
    segments, words = [], []
    for i, s in enumerate(data.get("transcription", [])):
        off = s.get("offsets", {})
        seg = _seg(i, s.get("text", ""), off.get("from", 0) / 1000.0, off.get("to", 0) / 1000.0)
        if not seg["text"]:
            continue
        segments.append(seg)
        # -ojf tokens are sub-word pieces; join pieces that do not start with a space.
        cur = None
        for tk in s.get("tokens", []):
            txt = tk.get("text", "")
            if txt.startswith("[_") or not txt.strip():
                continue
            o = tk.get("offsets", {})
            a, b, p = o.get("from", 0) / 1000.0, o.get("to", 0) / 1000.0, tk.get("p")
            if cur is None or txt.startswith(" "):
                if cur:
                    words.append(cur)
                cur = _word(txt, a, b, p, seg["id"])
            else:
                cur["text"] = _nfc(cur["text"] + txt)
                cur["endSec"] = round(max(cur["endSec"], b), 3)
        if cur:
            words.append(cur)
    return _finish(language, "whisper.cpp", segments, words)


_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")


def _ts(s: str) -> float:
    m = _TS.search(s)
    if not m:
        raise ValueError(f"bad timestamp {s!r}")
    h, mi, se, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(se) + int(ms.ljust(3, "0")) / 1000.0


def from_subtitles(text: str, language: str) -> Dict:
    """SRT or WebVTT -> phrase-level transcript (never word-reliable)."""
    blocks = re.split(r"\r?\n\s*\r?\n", text.replace("﻿", "").strip())
    segments = []
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        tl = next((k for k, ln in enumerate(lines) if "-->" in ln), None)
        if tl is None:
            continue
        a, z = lines[tl].split("-->")[:2]
        body = " ".join(re.sub(r"<[^>]+>", "", ln) for ln in lines[tl + 1:])
        if body.strip():
            segments.append(_seg(len(segments), body, _ts(a), _ts(z)))
    out = _finish(language, "subtitles(srt/vtt)", segments, [])
    out["reliabilityNotes"] = ["subtitle files carry phrase timings only; per-word highlight disabled"]
    return out


def _finish(language: str, producer: str, segments: List[Dict], words: List[Dict]) -> Dict:
    ok, reasons = sanity_check_words(words, segments) if words else (False, ["no word timings"])
    t = {"language": language, "timebase": "source", "wordTimestampsReliable": ok,
         "producer": producer, "segments": segments}
    if words:
        t["words"] = words
    t["reliabilityNotes"] = reasons or ["word timings passed sanity checks (still spot-check 3 words by ear)"]
    return t


def load_any(path, language: str = "vi") -> Dict:
    """Detect format from content. Returns transcript dict + 'reliabilityNotes' (strip it before
    validating against the strict schema, or keep it in a sidecar)."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() in (".srt", ".vtt") or raw.lstrip().startswith("WEBVTT") or "-->" in raw[:500]:
        return from_subtitles(raw, language)
    data = json.loads(raw)
    if isinstance(data, dict) and "timebase" in data and "wordTimestampsReliable" in data:  # already our format
        t = dict(data)
        if t.get("words"):
            ok, why = sanity_check_words(t["words"], t["segments"])
            if t["wordTimestampsReliable"] and not ok:
                t["wordTimestampsReliable"] = False
            t["reliabilityNotes"] = why or ["word timings passed sanity checks"]
        else:
            t["wordTimestampsReliable"] = False
            t["reliabilityNotes"] = ["no word timings"]
        return t
    if isinstance(data, dict) and "transcription" in data:
        return from_whisper_cpp(data, language)
    if isinstance(data, dict) and isinstance(data.get("language"), str) and len(data["language"]) == 2:
        language = data["language"]
    return from_whisper(data, language)


def strict(t: Dict) -> Dict:
    """Drop non-schema helper keys (reliabilityNotes) for schema validation / storage."""
    return {k: v for k, v in t.items() if k != "reliabilityNotes"}
