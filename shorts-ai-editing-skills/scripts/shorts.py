"""One-command Shorts editing — the entry point for agents (OpenCode, Codex, Claude) and humans.

  python scripts/shorts.py edit INPUT.mp4 --instruction "cắt đoạn thừa, phụ đề động, zoom vừa phải"
         [--transcript t.json|t.srt|t.vtt] [--asr auto|faster-whisper|none] [--asr-model small]
         [--language vi] [--project DIR] [--platforms tiktok,youtube-shorts,instagram-reels]
         [--intensity subtle|normal|dynamic] [--music bed.wav --music-license own|CC0|licensed --music-proof "..."]
         [--sfx-library library.json] [--detect-faces] [--max-revisions 2] [--no-export] [--detach]
  python scripts/shorts.py status PROJECT_DIR      # progress of a running/finished job (for agents)
  python scripts/shorts.py capabilities            # what this machine can do (JSON)

Writes everything to PROJECT_DIR/ai-edit/ (default: <input folder>/<input name>_shorts/):
  progress.jsonl (one JSON event per line), shorts.log, transcript.source.json, rev-<n>/... ,
  rev-<n>/run-report.json, rev-<n>/final.mp4. The input file is never modified.
Exit codes: 0 done (QA pass) · 3 done but QA findings remain · 2 bad input/setup · 1 crash.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator" / "lib"))
import runner as RN  # noqa: E402  (also puts core + skills libs on sys.path)
import sae_asr  # noqa: E402
import sae_env  # noqa: E402
import sae_transcribe  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402


class Progress:
    def __init__(self, ai_dir: Path, echo: bool = True):
        ai_dir.mkdir(parents=True, exist_ok=True)
        self.path = ai_dir / "progress.jsonl"
        self.echo = echo
        self.t0 = time.time()

    def __call__(self, stage: str, **kw) -> None:
        ev = {"t": round(time.time() - self.t0, 1), "stage": stage, **kw}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        if self.echo:
            extra = " ".join(f"{k}={v}" for k, v in kw.items() if k not in ("reasons",))
            print(f"[{ev['t']:>7.1f}s] {stage} {extra}", flush=True)


def default_project(inp: Path) -> Path:
    return inp.parent / f"{inp.stem}_shorts"


def cmd_capabilities(_a) -> int:
    m = sae_env.build_manifest()
    print(json.dumps({"facts": m.pop("_facts"), "capabilities": {k: v["status"] for k, v in m["capabilities"].items()}},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_status(a) -> int:
    ai = Path(a.project) / "ai-edit"
    pf = ai / "progress.jsonl"
    if not pf.is_file():
        print(json.dumps({"state": "not-started", "project": str(a.project)}))
        return 2
    evs = [json.loads(x) for x in pf.read_text(encoding="utf-8").splitlines() if x.strip()]
    starts = [i for i, e in enumerate(evs) if e["stage"] == "start"]
    evs = evs[starts[-1]:] if starts else evs  # only the latest run
    last = evs[-1]
    state = "done" if last["stage"] == "done" else "failed" if last["stage"] == "error" else "running"
    out = {"state": state, "last": last, "events": len(evs)}
    if state == "done" and last.get("report"):
        rep = load_json(last["report"])
        out.update(final=rep["final"], needsHuman=rep["needsHuman"],
                   revisions=[{k: r[k] for k in ("revision", "gate", "counts")} for r in rep["revisions"]])
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def build_request(a) -> dict:
    req = {"requestVersion": "1.0", "instruction": a.instruction, "language": a.language,
           "constraints": {"maxRemovedRatio": a.max_removed, "allowReorder": False, "allowMusic": bool(a.music),
                           "allowSfx": bool(a.sfx_library), "maxReviewIterations": a.max_revisions,
                           "requireApprovalBeforeExport": False, "forbiddenEffects": [x for x in a.forbid.split(",") if x]}}
    if a.music:
        req["constraints"].update(musicFile=str(Path(a.music).resolve()), musicLicense=a.music_license or "",
                                  musicLicenseProof=a.music_proof or "")
    intent = {}
    if a.intensity:
        intent["intensity"] = a.intensity
    if a.music:
        intent["music"] = True
    if a.sfx_library:
        intent["sfx"] = True
    if intent:
        req["intent"] = intent
    if a.music and a.music_license not in ("own", "CC0", "licensed"):
        raise SystemExit("--music needs --music-license own|CC0|licensed and --music-proof (no unlicensed music)")
    return req


def get_transcript(a, inp: Path, ai: Path, progress) -> dict:
    cache = ai / "transcript.source.json"
    if a.transcript:
        t = sae_asr.load_any(a.transcript, a.language)
        progress("transcript", source=str(a.transcript), wordReliable=t["wordTimestampsReliable"], notes=t.get("reliabilityNotes"))
    elif cache.is_file() and not a.re_asr:
        t = load_json(cache)
        progress("transcript", source="cache", wordReliable=t["wordTimestampsReliable"])
        return t
    elif a.asr != "none" and sae_transcribe.available():
        progress("transcribe", model=a.asr_model, language=a.language)
        t = sae_transcribe.transcribe(str(inp), a.language, a.asr_model, progress=progress)
        progress("transcript", source=f"faster-whisper:{a.asr_model}", wordReliable=t["wordTimestampsReliable"], notes=t.get("reliabilityNotes"))
    else:
        raise SystemExit("No transcript: pass --transcript <json|srt|vtt> or install faster-whisper "
                         "(pip install faster-whisper) and use --asr auto.")
    t = sae_asr.strict(t)
    errs = validate(t, load_json(ROOT / "core/schemas/transcript.schema.json"))
    if errs:
        raise SystemExit("transcript invalid: " + "; ".join(errs[:5]))
    RN._dump(t, cache)
    return t


def cmd_edit(a) -> int:
    inp = Path(a.input).resolve()
    if not inp.is_file():
        print(f"input not found: {inp}", file=sys.stderr)
        return 2
    project = Path(a.project).resolve() if a.project else default_project(inp)
    ai = project / "ai-edit"
    if a.detach:
        ai.mkdir(parents=True, exist_ok=True)
        args = [sys.executable, str(Path(__file__).resolve())] + [x for x in sys.argv[1:] if x != "--detach"]
        if "--project" not in args:
            args += ["--project", str(project)]
        log = open(ai / "shorts.log", "a", encoding="utf-8")
        kw = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL, "cwd": str(ROOT)}
        if os.name == "nt":
            kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
        p = subprocess.Popen(args, **kw)
        print(json.dumps({"detached": True, "pid": p.pid, "project": str(project),
                          "status": f'python "{Path(__file__).resolve()}" status "{project}"'}, ensure_ascii=False))
        return 0
    progress = Progress(ai)
    try:
        progress("start", input=str(inp), project=str(project), instruction=a.instruction)
        t = get_transcript(a, inp, ai, progress)
        import sae_media
        info = sae_media.probe_media(str(inp))
        manifest = load_json(a.manifest) if a.manifest else sae_env.build_manifest(
            fps=a.fps or (round(info["avgFrameRate"]) if 23 <= info["avgFrameRate"] <= 61 else 30),
            word_timestamps=t["wordTimestampsReliable"], detect_faces=a.detect_faces)
        manifest.pop("_facts", None)
        RN._dump(manifest, ai / "capability-manifest.json")
        reg = load_json(ROOT / "skills.registry.json")
        if a.vfx:
            for s in reg["skills"]:
                if s["id"] == "cinematic-vfx":
                    s["enabled"] = True
        req = build_request(a)
        sfx = load_json(a.sfx_library) if a.sfx_library else None
        assets = {}
        if sfx:
            base = Path(a.sfx_library).resolve().parent
            assets = {it["file"]: str((base / it["file"]).resolve()) if not Path(it["file"]).is_absolute() else it["file"]
                      for it in sfx["items"]}
        params = {"captions": {"platforms": [x for x in a.platforms.split(",") if x]}, "detectSubjects": a.detect_faces}
        if a.caption_style:
            params["captions"]["style"] = a.caption_style
        r = RN.Runner(req, manifest, reg, project, assets=assets, sfx_library=sfx, progress=progress)
        progress("plan", skills={s["id"]: f"{s['status']}:{s['mode']}" for s in r.orch["skills"]}, intensity=r.orch["intensity"],
                 warnings=r.orch.get("warnings", []))
        rep = r.run(str(inp), t, params=params, export=not a.no_export)
        print(json.dumps({"final": rep["final"], "needsHuman": rep["needsHuman"],
                          "report": str(Path(rep["revisions"][-1]["dir"]) / "run-report.json")}, ensure_ascii=False, indent=2))
        return 0 if rep["final"]["gate"] == "pass" else 3
    except SystemExit as e:
        progress("error", message=str(e))
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        progress("error", message=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
        raise


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("edit")
    e.add_argument("input")
    e.add_argument("--instruction", default="Edit video này theo phong cách Shorts chuyên nghiệp, cắt đoạn thừa, phụ đề động, "
                                            "zoom đoạn quan trọng, hiệu ứng vừa phải, giữ giọng nói rõ.")
    e.add_argument("--transcript")
    e.add_argument("--asr", default="auto", choices=["auto", "faster-whisper", "none"])
    e.add_argument("--asr-model", default="small")
    e.add_argument("--re-asr", action="store_true", help="ignore cached transcript")
    e.add_argument("--language", default="vi")
    e.add_argument("--project")
    e.add_argument("--manifest", help="audited editor manifest; default = auto-detect this machine")
    e.add_argument("--platforms", default="tiktok,youtube-shorts,instagram-reels")
    e.add_argument("--intensity", choices=["subtle", "normal", "dynamic"])
    e.add_argument("--caption-style", choices=["clean-bold", "punchy-3", "boxed-calm"])
    e.add_argument("--music")
    e.add_argument("--music-license", choices=["own", "CC0", "licensed"])
    e.add_argument("--music-proof")
    e.add_argument("--sfx-library")
    e.add_argument("--vfx", action="store_true", help="enable the opt-in VFX skill")
    e.add_argument("--forbid", default="camera-shake", help="comma list, e.g. camera-shake,zoom")
    e.add_argument("--max-removed", type=float, default=0.35)
    e.add_argument("--max-revisions", type=int, default=2)
    e.add_argument("--fps", type=float)
    e.add_argument("--detect-faces", action="store_true")
    e.add_argument("--no-export", action="store_true")
    e.add_argument("--detach", action="store_true", help="run in background; poll with `status`")
    e.set_defaults(fn=cmd_edit)
    s = sub.add_parser("status")
    s.add_argument("project")
    s.set_defaults(fn=cmd_status)
    c = sub.add_parser("capabilities")
    c.set_defaults(fn=cmd_capabilities)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
