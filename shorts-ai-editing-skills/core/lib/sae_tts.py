"""Local text-to-speech backends (no cloud, no paid API). One WAV per sentence -> exact timings.

Backends (pick with --tts):
  piper    : Piper TTS (MIT). `pip install piper-tts` + a voice model .onnx (Vietnamese voices exist,
             e.g. vi_VN-vais1000-medium). Most natural offline option.  --tts piper --tts-voice <model.onnx>
  sapi     : Windows built-in voices via PowerShell System.Speech. Vietnamese needs a Vietnamese SAPI
             voice installed (check: --tts sapi --list-voices).               --tts sapi [--tts-voice "<name>"]
  espeak   : espeak-ng (GPL, separate install). Robotic but always works.     --tts espeak
  test     : tone whose length follows the text (CI/tests only).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


def _run(cmd: List[str], inp: Optional[str] = None) -> str:
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"TTS command failed: {' '.join(cmd)[:200]}\n{r.stderr[-600:]}")
    return r.stdout


def duration(wav: str) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", wav])
    return float(json.loads(out)["format"]["duration"])


def list_voices(backend: str) -> List[str]:
    if backend == "sapi":
        ps = ("Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer)"
              ".GetInstalledVoices() | % { $_.VoiceInfo.Name + ' | ' + $_.VoiceInfo.Culture }")
        return [x for x in _run(["powershell", "-NoProfile", "-Command", ps]).splitlines() if x.strip()]
    if backend == "espeak":
        return [ln for ln in _run(["espeak-ng", "--voices=vi"]).splitlines()[1:]]
    return []


def available(backend: str) -> bool:
    if backend == "test":
        return bool(shutil.which("ffmpeg"))
    if backend == "piper":
        if shutil.which("piper"):
            return True
        try:
            import piper  # noqa: F401
            return True
        except ImportError:
            return False
    if backend == "sapi":
        return sys.platform.startswith("win") and bool(shutil.which("powershell"))
    if backend == "espeak":
        return bool(shutil.which("espeak-ng"))
    return False


def synth(text: str, out_wav: str, backend: str, voice: Optional[str] = None, lang: str = "vi", rate: float = 1.0) -> float:
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    if backend == "test":
        d = max(0.6, 0.065 * len(text) / rate)
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=180:duration={d:.3f}",
              "-af", "volume='0.4+0.4*sin(2*PI*5*t)':eval=frame", "-ar", "48000", "-ac", "1", out_wav])
    elif backend == "piper":
        if not voice:
            raise RuntimeError("piper needs --tts-voice <model.onnx>")
        exe = [shutil.which("piper")] if shutil.which("piper") else [sys.executable, "-m", "piper"]
        _run(exe + ["--model", voice, "--output_file", out_wav, "--length_scale", f"{1 / rate:.3f}"], inp=text)
    elif backend == "sapi":
        esc = text.replace("'", "''")
        sel = f"$s.SelectVoice('{voice}');" if voice else ""
        ps = (f"Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; {sel}"
              f"$s.Rate={int(round((rate - 1) * 10))}; $s.SetOutputToWaveFile('{out_wav}'); $s.Speak('{esc}'); $s.Dispose()")
        _run(["powershell", "-NoProfile", "-Command", ps])
    elif backend == "espeak":
        _run(["espeak-ng", "-v", voice or lang, "-s", str(int(165 * rate)), "-w", out_wav, text])
    else:
        raise ValueError(f"unknown TTS backend {backend}")
    return duration(out_wav)


def synth_sentences(sentences: List[str], out_dir: str, backend: str, voice: Optional[str] = None, lang: str = "vi",
                    gap: float = 0.25, rate: float = 1.0) -> Dict:
    """Synthesize each sentence, concatenate with `gap` s of silence. Returns voice.wav + timings."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    parts, t, timings = [], 0.0, []
    for i, s in enumerate(sentences):
        wav = d / f"s{i + 1:03d}.wav"
        dur = synth(s, str(wav), backend, voice, lang, rate)
        timings.append({"id": f"s{i + 1}", "text": s, "startSec": round(t, 3), "endSec": round(t + dur, 3)})
        parts.append(str(wav))
        t += dur + gap
    lst = Path(tempfile.mkdtemp()) / "list.txt"
    sil = d / "_gap.wav"
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
          "-t", f"{gap:.3f}", str(sil)])
    lines = []
    for p in parts:
        lines += [f"file '{Path(p).as_posix()}'", f"file '{sil.as_posix()}'"]
    lst.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    voice_wav = d / "voice.wav"
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
          "-ar", "48000", "-ac", "1", str(voice_wav)])
    return {"voice": str(voice_wav), "durationSec": round(t - gap, 3), "sentences": timings, "backend": backend}
