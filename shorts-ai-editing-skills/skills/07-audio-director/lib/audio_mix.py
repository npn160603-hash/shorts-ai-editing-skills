"""Skill 07 — Audio Editing Director (stdlib only; FFmpeg does the DSP).

- Speech: high-pass + optional conservative denoise + two-pass loudnorm to platform target.
- Music: only a user-supplied file with license metadata; deterministic ducking under speech
  via a volume envelope (no sidechain guesswork), fades, loop/trim to length.
- SFX: only from a local library whose items declare a license; anchored to visual events.
- Beat grid: lightweight energy-onset + autocorrelation tempo estimate (heuristic DSP,
  steady-beat music only) or user-given BPM.
Silence trimming is NOT done here (Skill 04 owns cuts) — no duplicate logic.
"""
from __future__ import annotations

import array
import json
import math
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

TARGETS = {
    "shorts":  {"integratedLufs": -14.0, "truePeakDb": -1.0, "lra": 9.0},
    "podcast": {"integratedLufs": -16.0, "truePeakDb": -1.5, "lra": 7.0},
}
ALLOWED_LICENSES = {"own", "CC0", "licensed"}


# ------------------------------------------------------------------ loudness
def parse_loudnorm_json(stderr: str) -> Dict[str, float]:
    """Parse the JSON block printed by: -af loudnorm=I=-14:TP=-1:LRA=9:print_format=json -f null -"""
    m = re.search(r"\{\s*\"input_i\".*?\}", stderr, re.S)
    if not m:
        raise ValueError("loudnorm JSON not found in ffmpeg output")
    d = json.loads(m.group(0))
    return {k: float(v) for k, v in d.items() if k != "normalization_type"}


def measure_cmd(path: str, t: Dict) -> List[str]:
    return ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
            f"loudnorm=I={t['integratedLufs']}:TP={t['truePeakDb']}:LRA={t['lra']}:print_format=json", "-f", "null", "-"]


def loudnorm_pass2(measured: Dict[str, float], t: Dict) -> str:
    return (f"loudnorm=I={t['integratedLufs']}:TP={t['truePeakDb']}:LRA={t['lra']}"
            f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}:linear=true")


def voice_chain(denoise: bool, highpass_hz: int = 80) -> str:
    parts = [f"highpass=f={highpass_hz}"]
    if denoise:
        parts.append("afftdn=nf=-25:tn=1")  # conservative; aggressive denoise sounds robotic
    return ",".join(parts)


# ------------------------------------------------------------------ ducking
def merge_speech(ranges: Sequence[Sequence[float]], bridge: float = 0.6) -> List[Tuple[float, float]]:
    rs = sorted((float(a), float(b)) for a, b in ranges)
    out: List[List[float]] = []
    for a, b in rs:
        if out and a - out[-1][1] <= bridge:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def duck_envelope_expr(speech: Sequence[Tuple[float, float]], duck_db: float, attack: float, release: float) -> str:
    """volume expression (eval=frame): 1.0 in gaps, 10^(duck_db/20) under speech, linear ramps.
    Ramps start `attack` s BEFORE speech so the first syllable is never masked."""
    g = 10 ** (duck_db / 20.0)
    env = "0"
    for a, b in speech:
        trap = f"clip(min((t-{a - attack:.3f})/{attack:.3f}\\,({b + release:.3f}-t)/{release:.3f})\\,0\\,1)"
        env = f"max({env}\\,{trap})"
    return f"1-{1 - g:.4f}*{env}"


def duck_gain_at(t: float, speech: Sequence[Tuple[float, float]], duck_db: float, attack: float, release: float) -> float:
    g = 10 ** (duck_db / 20.0)
    env = 0.0
    for a, b in speech:
        env = max(env, min(max(min((t - (a - attack)) / attack, ((b + release) - t) / release), 0.0), 1.0))
    return 1 - (1 - g) * env


# ------------------------------------------------------------------ SFX
def validate_library(lib: Dict) -> List[str]:
    errs = []
    for it in lib.get("items", []):
        if it.get("license") not in ALLOWED_LICENSES:
            errs.append(f"{it.get('id')}: license '{it.get('license')}' not allowed")
        if not it.get("licenseProof"):
            errs.append(f"{it.get('id')}: missing licenseProof")
    return errs


def place_sfx(anchors: Sequence[Dict], lib: Dict, speech: Sequence[Tuple[float, float]], duration: float,
              max_per_10s: float = 2.0, min_gap: float = 1.5) -> Tuple[List[Dict], List[str]]:
    """anchors: [{type: transition|keyword-pop|callout, atSec, ref}] -> sfx events.
    Category map: transition->whoosh (starts 0.12 s before), keyword-pop->pop, callout->tick."""
    usable = {it["category"]: it for it in lib.get("items", [])
              if it.get("license") in ALLOWED_LICENSES and it.get("licenseProof")}
    cat_for = {"transition": "whoosh", "keyword-pop": "pop", "callout": "tick"}
    lead = {"whoosh": 0.12, "pop": 0.0, "tick": 0.0}
    out, notes = [], []
    for a in sorted(anchors, key=lambda x: x["atSec"]):
        cat = cat_for.get(a["type"])
        it = usable.get(cat)
        if not it:
            notes.append(f"no licensed '{cat}' sfx in library for {a['type']}@{a['atSec']}")
            continue
        at = max(0.0, a["atSec"] - lead[cat])
        if at + it["durationSec"] > duration:
            continue
        if out and at - out[-1]["atSec"] < min_gap:
            notes.append(f"sfx@{at:.2f} dropped: min gap")
            continue
        if sum(1 for e in out if abs(e["atSec"] - at) < 5.0) >= max_per_10s:
            notes.append(f"sfx@{at:.2f} dropped: budget")
            continue
        over_speech = any(s < at + it["durationSec"] and at < e for s, e in speech)
        gain = -14.0 if over_speech else -8.0  # CR-07: well under the voice when overlapping words
        out.append({"id": f"sfx{len(out) + 1:02d}", "file": it["file"], "category": cat, "license": it["license"],
                    "atSec": round(at, 3), "gainDb": gain, "anchor": {"type": a["type"], "ref": str(a.get("ref", ""))}})
    return out, notes


# ------------------------------------------------------------------ beat grid
def _onset_envelope(samples: Sequence[float], hop: int) -> List[float]:
    n = len(samples) // hop
    env, prev = [], 0.0
    for i in range(n):
        seg = samples[i * hop:(i + 1) * hop]
        e = math.sqrt(sum(x * x for x in seg) / hop)
        env.append(max(0.0, e - prev))  # positive energy flux = onsets
        prev = e
    mean = sum(env) / max(len(env), 1)
    return [x - mean for x in env]


def _acf(env: Sequence[float], lag: float) -> float:
    """Autocorrelation at a fractional lag (linear interpolation)."""
    l0 = int(lag)
    fr = lag - l0
    s = 0.0
    for i in range(l0 + 1, len(env)):
        s += env[i] * ((1 - fr) * env[i - l0] + fr * env[i - l0 - 1])
    return s


def estimate_bpm(samples: Sequence[float], sr: int, lo: float = 70, hi: float = 180) -> Tuple[float, float, float]:
    """Energy-flux onset envelope + fractional-lag autocorrelation (with 2x-lag support).
    Returns (bpm, offsetSec, confidence 0..1). Heuristic DSP: reliable for steady-beat music,
    unreliable for rubato/ambient -> callers must check confidence (>= 0.3)."""
    hop = 256
    env = _onset_envelope(samples, hop)
    if len(env) < 32:
        return 0.0, 0.0, 0.0
    fr = sr / hop
    cands = []
    for bpm10 in range(int(lo * 10), int(hi * 10) + 1, 5):
        lag = fr * 60.0 / (bpm10 / 10.0)
        if 2 * lag + 2 >= len(env):
            continue
        cands.append((_acf(env, lag) + 0.5 * _acf(env, 2 * lag), bpm10 / 10.0))
    if not cands:
        return 0.0, 0.0, 0.0
    best_val, best_bpm = max(cands)
    vals = sorted(v for v, _ in cands)
    median = vals[len(vals) // 2]
    conf = max(0.0, min(1.0, (best_val - median) / (abs(best_val) + 1e-9))) if best_val > 0 else 0.0
    period = fr * 60.0 / best_bpm
    phase = []
    for p in range(int(period)):
        k_max = int((len(env) - 1 - p) / period)
        phase.append(sum(env[int(round(k * period + p))] for k in range(k_max + 1)))
    off = phase.index(max(phase)) / fr if phase else 0.0
    return round(best_bpm, 1), round(off, 3), round(conf, 2)


def read_pcm_s16le(path: str) -> array.array:
    """Read mono s16le produced by: ffmpeg -i music.mp3 -ac 1 -ar 11025 -f s16le music.raw"""
    a = array.array("h")
    with open(path, "rb") as f:
        a.frombytes(f.read())
    if sys.byteorder == "big":
        a.byteswap()
    return a


def beat_grid(bpm: float, offset: float, duration: float) -> List[float]:
    if bpm <= 0:
        return []
    p = 60.0 / bpm
    out, t = [], offset
    while t < duration:
        out.append(round(t, 3))
        t += p
    return out


# ------------------------------------------------------------------ plan & graph
def build_plan(duration: float, speech: Sequence[Sequence[float]], caps: Dict[str, str], *, platform: str = "shorts",
               speech_priority: bool = True, music: Optional[Dict] = None, sfx_lib: Optional[Dict] = None,
               anchors: Sequence[Dict] = (), max_sfx_per_10s: float = 2.0, beat: Optional[Dict] = None) -> Dict:
    ok = lambda k: caps.get(k) == "implemented"  # noqa: E731
    warnings: List[str] = []
    sp = merge_speech(speech)
    plan: Dict = {"audioMixPlanVersion": "1.0", "timebase": "output", "durationSec": round(duration, 3),
                  "targets": TARGETS[platform],
                  "voice": {"chain": voice_chain(denoise=speech_priority and ok("audio.denoise")),
                            "loudnorm": "two-pass" if ok("audio.loudnorm") else "none"},
                  "cutFadeMs": 10,
                  "music": None, "sfx": [], "warnings": warnings}
    if not ok("audio.loudnorm"):
        warnings.append("loudnorm not implemented: output loudness not normalised (QA will measure)")
    if music:
        if music.get("license") not in ALLOWED_LICENSES or not music.get("licenseProof"):
            warnings.append("music rejected: missing/unknown license")
        elif not ok("audio.duck"):
            warnings.append("music skipped: audio.duck not implemented (music under speech without ducking hurts clarity)")
        else:
            plan["music"] = {"file": music["file"], "license": music["license"], "gainDb": music.get("gainDb", -18.0),
                             "duckDb": music.get("duckDb", -12.0 if speech_priority else -8.0),
                             "attackSec": 0.25, "releaseSec": 0.45, "fadeInSec": 0.6, "fadeOutSec": 1.2,
                             "duckRanges": [[round(a, 3), round(b, 3)] for a, b in sp]}
    if sfx_lib is not None:
        errs = validate_library(sfx_lib)
        warnings += [f"sfx library: {e}" for e in errs]
        if ok("audio.mixSfx"):
            ev, notes = place_sfx(anchors, sfx_lib, sp, duration, max_sfx_per_10s)
            plan["sfx"] = ev
            warnings += notes
    if beat:
        plan["beatGrid"] = beat
    return plan


def ffmpeg_mix_graph(plan: Dict, measured: Optional[Dict[str, float]] = None, voice_label: str = "[0:a]",
                     music_input: int = 1, sfx_first_input: int = 2) -> str:
    """filter_complex for the final mix -> [amix]. Inputs: 0 = cut video (voice), 1 = music
    (use -stream_loop -1 on that input), then one input per SFX event in plan order."""
    d = plan["durationSec"]
    parts = [f"{voice_label}{plan['voice']['chain']}[vox]"]
    labels = ["[vox]"]
    m = plan.get("music")
    if m:
        env = duck_envelope_expr([tuple(r) for r in m["duckRanges"]], m["duckDb"], m["attackSec"], m["releaseSec"])
        parts.append(f"[{music_input}:a]atrim=duration={d:.3f},asetpts=PTS-STARTPTS,volume={m['gainDb']}dB,"
                     f"volume='{env}':eval=frame,afade=t=in:d={m['fadeInSec']},"
                     f"afade=t=out:st={max(0.0, d - m['fadeOutSec']):.3f}:d={m['fadeOutSec']}[mus]")
        labels.append("[mus]")
    for i, s in enumerate(plan.get("sfx", [])):
        ms = int(round(s["atSec"] * 1000))
        parts.append(f"[{sfx_first_input + i}:a]volume={s['gainDb']}dB,adelay={ms}|{ms}[sx{i}]")
        labels.append(f"[sx{i}]")
    if len(labels) > 1:
        parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0[pre]")
    else:
        parts.append("[vox]anull[pre]")
    tail = loudnorm_pass2(measured, plan["targets"]) if (measured and plan["voice"]["loudnorm"] == "two-pass") else "anull"
    parts.append(f"[pre]{tail},aresample=48000[amix]")
    return ";".join(parts)
