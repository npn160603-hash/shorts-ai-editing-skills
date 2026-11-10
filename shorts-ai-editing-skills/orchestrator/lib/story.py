"""Story mode: script -> voice (TTS or your recording) -> one licensed scene per sentence -> base video.

The base video + its transcript then go through the normal Runner (captions, camera, transitions,
audio, QA). Scenes come ONLY from a local library of licensed clips (e.g. folders made by
tools/fetch_stock.py with credits.json) or files you name explicitly — every used clip is written
to credits.json/credits.txt next to the video.

Script format (UTF-8 text):
    Bạn đang lãng phí 2 giờ mỗi ngày? [scene: phone scrolling night]
    Đây là 3 mẹo giúp bạn lấy lại thời gian.
    Mẹo số một: tắt thông báo. [clip: D:/my-footage/desk.mp4]
`[scene: ...]` = search words for the library (English finds more stock); `[clip: path]` = exact file.
Without a tag the sentence's own keywords are used.
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

import director as D
import sae_tts

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
TAG = re.compile(r"\[(scene|clip)\s*:\s*([^\]]+)\]", re.I)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse_script(text: str) -> List[Dict]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tags = {k.lower(): v.strip() for k, v in TAG.findall(line)}
        body = TAG.sub("", line).strip()
        parts = re.findall(r"[^.!?…]+[.!?…]*", body) or [body]
        parts = [p.strip() for p in parts if p.strip()]
        for k, p in enumerate(parts):
            out.append({"text": p, "scene": tags.get("scene") if k == 0 else None, "clip": tags.get("clip") if k == 0 else None})
    return out


def load_library(dirs: List[str]) -> List[Dict]:
    """Clips + metadata. credits.json (from fetch_stock) gives query/author/licence; other files are
    indexed by folder/file name and must be your own footage (licence 'own')."""
    lib, seen = [], set()
    for d in dirs:
        base = Path(d)
        cj = base / "credits.json"
        meta = {}
        if cj.is_file():
            for r in json.loads(cj.read_text(encoding="utf-8")):
                meta[str(Path(r["file"]).resolve()).lower()] = r
        for f in sorted(base.rglob("*")):
            if f.suffix.lower() not in VIDEO_EXT | IMAGE_EXT or not f.is_file():
                continue
            key = str(f.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            m = meta.get(key, {})
            words = set(re.findall(r"[a-z0-9]{3,}", fold(" ".join([m.get("query", ""), f.parent.name, f.stem]))))
            lib.append({"file": str(f.resolve()), "kind": "image" if f.suffix.lower() in IMAGE_EXT else "video",
                        "words": sorted(words), "source": m.get("source", "local"), "author": m.get("author", ""),
                        "pageUrl": m.get("pageUrl", ""), "license": m.get("license", "own (your footage — confirm)"),
                        "durationSec": float(m.get("durationSec") or 0)})
    return lib


def pick_scene(sentence: Dict, lib: List[Dict], used: Dict[str, int]) -> Optional[Dict]:
    if sentence.get("clip"):
        p = Path(sentence["clip"])
        if not p.is_file():
            raise FileNotFoundError(f"[clip: {p}] not found")
        return {"file": str(p.resolve()), "kind": "image" if p.suffix.lower() in IMAGE_EXT else "video", "words": [],
                "source": "explicit", "author": "", "pageUrl": "", "license": "own/explicit (confirm)", "durationSec": 0}
    if not lib:
        return None
    query = sentence.get("scene") or " ".join(D.keyword_candidates(sentence["text"])) or sentence["text"]
    q = set(re.findall(r"[a-z0-9]{3,}", fold(query)))
    best = max(lib, key=lambda c: (len(q & set(c["words"])) * 2 - used.get(c["file"], 0) * 1.5, -used.get(c["file"], 0)))
    return best


def _dur(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return 0.0


def assemble(sentences: List[Dict], voice: Dict, scenes: List[Optional[Dict]], out_dir: Path,
             width: int = 1080, height: int = 1920, fps: int = 30) -> Dict:
    """One shot per sentence (covering the sentence + the gap after it), cover-cropped to 9:16,
    concatenated and muxed with the voice track. Missing scene -> dark card (never someone else's clip)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    inputs, filters, labels, used_credits = [], [], [], []
    idx = 0
    times = voice["sentences"]
    total = voice["durationSec"]
    for i, (t, sc) in enumerate(zip(times, scenes)):
        start = t["startSec"]
        end = times[i + 1]["startSec"] if i + 1 < len(times) else total
        d = max(0.2, end - start)
        fit = (f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
               f"fps={fps},setsar=1,format=yuv420p,trim=duration={d:.3f},setpts=PTS-STARTPTS")
        k = idx
        idx += 1
        if sc is None:
            inputs += ["-f", "lavfi", "-i", f"color=c=0x111318:s={width}x{height}:r={fps}:d={d:.3f}"]
            filters.append(f"[{k}:v]{fit}[v{i}]")
        elif sc["kind"] == "image":
            inputs += ["-loop", "1", "-t", f"{d:.3f}", "-i", sc["file"]]
            filters.append(f"[{k}:v]{fit}[v{i}]")
        else:
            cd = sc.get("durationSec") or _dur(sc["file"])
            offset = 0.5 if cd > d + 1.0 else 0.0
            loop = ["-stream_loop", "-1"] if cd and cd < d + offset else []
            inputs += loop + ["-ss", f"{offset:.2f}", "-i", sc["file"]]
            filters.append(f"[{k}:v]{fit}[v{i}]")
        labels.append(f"[v{i}]")
        if sc:
            used_credits.append({"sentence": t["text"], "atSec": round(start, 3), **{k2: sc[k2] for k2 in ("file", "source", "author", "pageUrl", "license")}})
    k = idx
    inputs += ["-i", voice["voice"]]
    graph = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[v]"
    base = out_dir / "base.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", *inputs, "-filter_complex", graph, "-map", "[v]", "-map", f"{k}:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", str(base)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("assemble failed: " + r.stderr[-1500:])
    (out_dir / "credits.json").write_text(json.dumps(used_credits, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"{c['atSec']:>7.2f}s  {c['source']}  {c['author'] or '-'}  {c['pageUrl'] or c['file']}  [{c['license']}]" for c in used_credits]
    (out_dir / "credits.txt").write_text("Nguồn cảnh / Footage credits\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return {"base": str(base), "credits": str(out_dir / "credits.json"), "missingScenes": sum(1 for s in scenes if s is None)}


def transcript_from_voice(voice: Dict, lang: str) -> Dict:
    """Sentence timings are exact (one WAV per sentence). Word timings are NOT known -> phrase captions,
    unless the caller re-transcribes voice.wav with faster-whisper for word-level highlight."""
    segs = [{"id": s["id"], "text": s["text"], "startSec": s["startSec"], "endSec": s["endSec"]} for s in voice["sentences"]]
    return {"language": lang, "timebase": "source", "wordTimestampsReliable": False, "producer": f"tts:{voice['backend']}",
            "segments": segs}
