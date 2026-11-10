"""Optional local ASR with faster-whisper (MIT). Produces the shared Transcript format.

    pip install faster-whisper          # first run downloads the model (~150 MB for 'small')

Never required: if faster-whisper is missing, callers pass an existing transcript/SRT instead.
Model choice for Vietnamese: 'small' (fast, OK) / 'medium' (better) / 'large-v3' (best, slow on CPU).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

import sae_asr


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def segments_to_whisper_json(segments, language: str) -> Dict:
    """faster-whisper Segment objects (with .words) -> openai-whisper-like dict."""
    out = []
    for s in segments:
        words = [{"word": w.word, "start": w.start, "end": w.end, "probability": getattr(w, "probability", None)}
                 for w in (getattr(s, "words", None) or [])]
        out.append({"start": s.start, "end": s.end, "text": s.text, "words": words})
    return {"language": language, "segments": out}


def transcribe(media_path: str, language: str = "vi", model: str = "small", device: str = "auto",
               compute_type: str = "int8", progress: Optional[Callable] = None) -> Dict:
    if not available():
        raise RuntimeError("faster-whisper not installed. Either `pip install faster-whisper` "
                           "or pass --transcript <file.json|.srt|.vtt>.")
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device=device, compute_type=compute_type)
    segs, info = m.transcribe(media_path, language=language, word_timestamps=True, vad_filter=True,
                              condition_on_previous_text=False)
    collected = []
    for s in segs:  # generator: decoding happens while iterating
        collected.append(s)
        if progress:
            progress("transcribe", atSec=round(s.end, 1), totalSec=round(getattr(info, "duration", 0) or 0, 1))
    t = sae_asr.from_whisper(segments_to_whisper_json(collected, language), language, producer=f"faster-whisper:{model}")
    return t
