"""Optional local LLM via Ollama (http://localhost:11434). Never required; every answer is validated.

    ollama pull qwen2.5:7b        # or llama3.1:8b, gemma2:9b … (check each model's licence)
    python scripts/shorts.py edit v.mp4 --llm qwen2.5:7b

Used for: segment roles/keywords (Skill 01 ai_overrides), highlight re-ranking (clips mode),
title/description ideas (publish kit). Output is parsed as JSON and checked by the caller
(keywords must occur in the transcript, numbers clamped, enums enforced).
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List, Optional

URL = "http://localhost:11434/api/generate"


def ask_json(model: str, prompt: str, url: str = URL, timeout: float = 120.0, http=None) -> Any:
    body = json.dumps({"model": model, "prompt": prompt, "format": "json", "stream": False,
                       "options": {"temperature": 0.2}}).encode("utf-8")
    if http:
        raw = http(url, body)
    else:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
    return json.loads(json.loads(raw)["response"])


def available(url: str = "http://localhost:11434/api/tags") -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def segment_overrides(model: str, segments: List[Dict], http=None) -> Dict[str, Dict]:
    lines = "\n".join(f'{s["id"]}: {s["text"]}' for s in segments)
    prompt = ("Bạn là biên tập viên video ngắn. Với mỗi câu (id: text) dưới đây, trả JSON dạng "
              '{"<id>": {"role": "hook|setup|point|proof|climax|payoff|cta", "importance": 0..1, '
              '"keywords": ["cụm có NGUYÊN VĂN trong câu"], "sincere": true|false}}. Tối đa 2 keyword/câu. '
              "Chỉ trả JSON.\n\n" + lines)
    data = ask_json(model, prompt, http=http)
    return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def rate_highlights(model: str, clips: List[Dict], http=None) -> Dict[int, float]:
    lines = "\n".join(f"{i}: {c['firstSentence']} … ({c['durationSec']:.0f}s, keywords: {', '.join(c['keywords'])})"
                      for i, c in enumerate(clips))
    prompt = ('Chấm mức hấp dẫn để làm video ngắn độc lập cho từng đoạn (0..1). Trả JSON {"<index>": số}. '
              "Chỉ trả JSON.\n\n" + lines)
    data = ask_json(model, prompt, http=http)
    out = {}
    for k, v in (data.items() if isinstance(data, dict) else []):
        try:
            out[int(k)] = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            continue
    return out


def title_ideas(model: str, transcript_text: str, n: int = 3, http=None) -> List[str]:
    prompt = (f'Đề xuất {n} tiêu đề YouTube Shorts tiếng Việt (≤ 70 ký tự), đúng nội dung, không giật tít sai sự thật. '
              f'Trả JSON {{"titles": [..]}}.\n\nNội dung:\n{transcript_text[:3000]}')
    data = ask_json(model, prompt, http=http)
    ts = data.get("titles", []) if isinstance(data, dict) else []
    return [str(t).strip()[:70] for t in ts if str(t).strip()][:n]
