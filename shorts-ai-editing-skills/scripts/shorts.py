"""One-command Shorts editing — the entry point for agents (OpenCode, Codex, Claude) and humans.

  python scripts/shorts.py edit INPUT.mp4 --instruction "cắt đoạn thừa, phụ đề động, zoom vừa phải"
         [--transcript t.json|t.srt|t.vtt] [--asr auto|faster-whisper|none] [--asr-model small]
         [--language vi] [--project DIR] [--platforms tiktok,youtube-shorts,instagram-reels]
         [--intensity subtle|normal|dynamic] [--music bed.wav --music-license own|CC0|licensed --music-proof "..."]
         [--sfx-library library.json] [--detect-faces] [--max-revisions 2] [--no-export] [--detach]
  python scripts/shorts.py clips LONG.mp4 --count 5 [--min-sec 20 --max-sec 60]   # long video -> several Shorts
  python scripts/shorts.py story script.txt [--tts piper --tts-voice vi.onnx | --voice my.wav] --library D:\\sources [--fetch]
  python scripts/shorts.py batch FOLDER            # every video in a folder (sidecar .srt/.json used)
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


def _detach(project: Path) -> int:
    ai = project / "ai-edit"
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


def _params(a) -> dict:
    ht = getattr(a, "hook_title", "auto")
    params = {"captions": {"platforms": [x for x in a.platforms.split(",") if x]}, "detectSubjects": a.detect_faces,
              "overlays": {"hookTitle": None if ht == "none" else ht, "keywordCallouts": not a.no_callouts,
                           "progressBar": not a.no_progress_bar, "cta": a.cta},
              "llm": a.llm, "beatSync": not a.no_beat_sync, "publish": not a.no_publish}
    if a.caption_style:
        params["captions"]["style"] = a.caption_style
    return params


def run_core(a, inp: Path, project: Path, transcript: dict, progress, extra_params: dict = None) -> dict:
    """Shared by edit / clips / story / batch: manifest -> Runner -> report."""
    import sae_media
    ai = project / "ai-edit"
    info = sae_media.probe_media(str(inp))
    manifest = load_json(a.manifest) if a.manifest else sae_env.build_manifest(
        fps=a.fps or (round(info["avgFrameRate"]) if 23 <= info["avgFrameRate"] <= 61 else 30),
        word_timestamps=transcript["wordTimestampsReliable"], detect_faces=a.detect_faces)
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
    params = _params(a)
    params.update(extra_params or {})
    if a.llm:
        import sae_llm
        if not sae_llm.available():
            progress("llm", warning="Ollama not reachable on localhost:11434 -> heuristics only")
            params["llm"] = None
    r = RN.Runner(req, manifest, reg, project, assets=assets, sfx_library=sfx, progress=progress)
    progress("plan", skills={s["id"]: f"{s['status']}:{s['mode']}" for s in r.orch["skills"]}, intensity=r.orch["intensity"],
             warnings=r.orch.get("warnings", []))
    return r.run(str(inp), transcript, params=params, export=not a.no_export)


def _summary(rep: dict) -> dict:
    return {"final": rep["final"], "needsHuman": rep["needsHuman"],
            "report": str(Path(rep["revisions"][-1]["dir"]) / "run-report.json")}


def _guard(progress, fn):
    try:
        return fn()
    except SystemExit as e:
        progress("error", message=str(e))
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        progress("error", message=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
        raise


def cmd_edit(a) -> int:
    inp = Path(a.input).resolve()
    if not inp.is_file():
        print(f"input not found: {inp}", file=sys.stderr)
        return 2
    project = Path(a.project).resolve() if a.project else default_project(inp)
    if a.detach:
        return _detach(project)
    progress = Progress(project / "ai-edit")

    def go():
        progress("start", mode="edit", input=str(inp), project=str(project), instruction=a.instruction)
        t = get_transcript(a, inp, project / "ai-edit", progress)
        rep = run_core(a, inp, project, t, progress)
        print(json.dumps(_summary(rep), ensure_ascii=False, indent=2))
        return 0 if rep["final"]["gate"] == "pass" else 3
    return _guard(progress, go)


def cmd_clips(a) -> int:
    """Long video -> several Shorts."""
    import highlights as HL
    inp = Path(a.input).resolve()
    if not inp.is_file():
        print(f"input not found: {inp}", file=sys.stderr)
        return 2
    project = Path(a.project).resolve() if a.project else inp.parent / f"{inp.stem}_clips"
    if a.detach:
        return _detach(project)
    progress = Progress(project / "ai-edit")

    def go():
        progress("start", mode="clips", input=str(inp), project=str(project), count=a.count)
        t = get_transcript(a, inp, project / "ai-edit", progress)
        bonus = None
        if a.llm:
            import sae_llm
            if sae_llm.available():
                pre = HL.find_highlights(t, a.count * 3, a.min_sec, a.max_sec)
                try:
                    rated = sae_llm.rate_highlights(a.llm, pre["clips"])
                    table = {(c["startSec"], c["endSec"]): (rated.get(i, 0.5) - 0.5) * 2 for i, c in enumerate(pre["clips"])}
                    bonus = lambda c: table.get((c["startSec"], c["endSec"]), 0.0)  # noqa: E731
                except Exception as e:  # noqa: BLE001
                    progress("llm", error=str(e)[:200])
        hl = HL.find_highlights(t, a.count, a.min_sec, a.max_sec, bonus=bonus)
        RN._dump(hl, project / "highlights.json")
        progress("highlights", found=hl["count"], considered=hl["candidatesConsidered"],
                 clips=[(c["id"], c["startSec"], c["endSec"], c["score"]) for c in hl["clips"]])
        results = []
        for c in hl["clips"]:
            clip_file = project / "clips" / f"{c['id']}.mp4"
            clip_file.parent.mkdir(parents=True, exist_ok=True)
            pad = 0.15
            start = max(0.0, c["startSec"] - pad)
            if not clip_file.exists():
                progress("extract", clip=c["id"], startSec=c["startSec"], endSec=c["endSec"])
                subprocess.run(HL.extract_cmd(str(inp), c["startSec"], c["endSec"], str(clip_file), pad), check=True)
            ct = HL.slice_transcript(t, c["startSec"], c["endSec"], offset=start)
            sub = project / "clips" / f"{c['id']}_shorts"
            RN._dump(ct, sub / "ai-edit" / "transcript.source.json")
            rep = run_core(a, clip_file, sub, ct, Progress(sub / "ai-edit", echo=False))
            progress("clip-done", clip=c["id"], gate=rep["final"]["gate"], final=rep["final"]["path"])
            results.append({"clip": c["id"], "startSec": c["startSec"], "endSec": c["endSec"], "score": c["score"],
                            "reasons": c["reasons"], **_summary(rep)})
        RN._dump({"clips": results}, project / "clips-report.json")
        progress("done", report=None, clips=len(results), summary=str(project / "clips-report.json"),
                 gate="pass" if all(r["final"]["gate"] == "pass" for r in results) else "fail")
        print(json.dumps({"clips": [{k: r[k] for k in ("clip", "startSec", "endSec", "final")} for r in results],
                          "report": str(project / "clips-report.json")}, ensure_ascii=False, indent=2))
        return 0 if results and all(r["final"]["gate"] == "pass" for r in results) else 3
    return _guard(progress, go)


def cmd_story(a) -> int:
    """Script -> voice -> licensed scenes -> base video -> normal edit."""
    import sae_tts
    import story as ST
    script = Path(a.script).resolve()
    if not script.is_file():
        print(f"script not found: {script}", file=sys.stderr)
        return 2
    project = Path(a.project).resolve() if a.project else script.parent / f"{script.stem}_story"
    if a.detach:
        return _detach(project)
    progress = Progress(project / "ai-edit")

    def go():
        progress("start", mode="story", script=str(script), project=str(project))
        sents = ST.parse_script(script.read_text(encoding="utf-8"))
        if not sents:
            raise SystemExit("script is empty")
        n = 1
        while (project / "story" / f"run-{n}").exists():
            n += 1
        work = project / "story" / f"run-{n}"  # each run gets its own voice/base/credits (never overwritten)
        if a.voice:
            vt = sae_asr.load_any(a.voice_transcript, a.language) if a.voice_transcript else None
            if vt is None:
                if not sae_transcribe.available():
                    raise SystemExit("--voice needs --voice-transcript <srt/json> or faster-whisper installed")
                vt = sae_transcribe.transcribe(a.voice, a.language, a.asr_model, progress=progress)
            vt = sae_asr.strict(vt)
            voice = {"voice": str(Path(a.voice).resolve()), "durationSec": sae_tts.duration(a.voice), "backend": "recorded",
                     "sentences": [{"id": s["id"], "text": s["text"], "startSec": s["startSec"], "endSec": s["endSec"]} for s in vt["segments"]]}
            transcript = vt
            scene_sents = [{"text": s["text"], "scene": None, "clip": None} for s in vt["segments"]]
            for k, s in enumerate(sents[: len(scene_sents)]):  # reuse [scene:] tags in script order when counts match
                if len(sents) == len(scene_sents):
                    scene_sents[k].update(scene=s["scene"], clip=s["clip"])
        else:
            if not sae_tts.available(a.tts):
                raise SystemExit(f"TTS backend '{a.tts}' not available (see core/lib/sae_tts.py for setup) or pass --voice")
            progress("tts", backend=a.tts, sentences=len(sents))
            voice = sae_tts.synth_sentences([s["text"] for s in sents], str(work / "voice"), a.tts, a.tts_voice, a.language,
                                            rate=a.tts_rate)
            transcript = ST.transcript_from_voice(voice, a.language)
            scene_sents = sents
        lib = ST.load_library(a.library or [])
        if a.fetch:
            import fetch_stock as FS
            keys = {"pexels": os.environ.get("PEXELS_API_KEY", ""), "pixabay": os.environ.get("PIXABAY_API_KEY", "")}
            for s in scene_sents:
                q = s.get("scene")
                if not q or s.get("clip"):
                    continue
                qw = set(__import__("re").findall(r"[a-z0-9]{3,}", ST.fold(q)))
                if any(len(qw & set(c["words"])) >= max(1, len(qw) // 2) for c in lib):
                    continue
                for src, key in keys.items():
                    if not key:
                        continue
                    fn = FS.search_pexels if src == "pexels" else FS.search_pixabay
                    try:
                        cands = fn(key, q, 2, True, 3, 60)
                    except Exception as e:  # noqa: BLE001
                        progress("fetch", source=src, query=q, error=str(e)[:150])
                        continue
                    rows = []
                    for c in cands:
                        dest = project / "sources" / FS.slug(q) / f"{src}_{c['id']}.mp4"
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        c["file"] = str(dest)
                        FS.download(c["url"], dest)
                        rows.append(c)
                    if rows:
                        FS.append_credits(project / "sources", rows)
                        progress("fetch", source=src, query=q, clips=len(rows))
                        break
            lib = ST.load_library((a.library or []) + [str(project / "sources")])
        used, scenes = {}, []
        for s in scene_sents:
            c = ST.pick_scene(s, lib, used)
            if c:
                used[c["file"]] = used.get(c["file"], 0) + 1
            scenes.append(c)
        res = ST.assemble(scene_sents, voice, scenes, work)
        progress("assembled", base=res["base"], missingScenes=res["missingScenes"], library=len(lib))
        credits = json.loads(Path(res["credits"]).read_text(encoding="utf-8"))
        rep = run_core(a, Path(res["base"]), project, sae_asr.strict(transcript), progress, {"credits": credits})
        out = _summary(rep)
        out["credits"] = str(work / "credits.txt")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if rep["final"]["gate"] == "pass" else 3
    return _guard(progress, go)


VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def cmd_batch(a) -> int:
    folder = Path(a.folder).resolve()
    vids = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and p.is_file())
    rows = []
    for v in vids:
        proj = default_project(v)
        done = list((proj / "ai-edit").glob("rev-*/final.mp4"))
        if done and not a.redo:
            rows.append({"video": v.name, "state": "skipped (already has final)", "final": str(sorted(done)[-1])})
            continue
        side = next((v.with_suffix(ext) for ext in (".json", ".srt", ".vtt") if v.with_suffix(ext).is_file()), None)
        a.input, a.project, a.transcript = str(v), None, str(side) if side else None
        print(f"=== {v.name} ===", flush=True)
        code = cmd_edit(a)
        rep = sorted((proj / "ai-edit").glob("rev-*/run-report.json"))
        final = load_json(rep[-1])["final"] if rep else {}
        rows.append({"video": v.name, "state": {0: "pass", 3: "done-with-findings", 2: "input/setup error"}.get(code, f"exit {code}"),
                     "final": final.get("path")})
    out = folder / f"batch-report-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    import csv
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["video", "state", "final"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"videos": len(vids), "report": str(out), "rows": rows}, ensure_ascii=False, indent=2))
    return 0 if all(r["state"] in ("pass", "skipped (already has final)") for r in rows) else 3


def _common(p, default_instr=True) -> None:
    if default_instr:
        p.add_argument("--instruction", default="Edit video này theo phong cách Shorts chuyên nghiệp, cắt đoạn thừa, phụ đề động, "
                                                "zoom đoạn quan trọng, hiệu ứng vừa phải, giữ giọng nói rõ.")
    p.add_argument("--transcript")
    p.add_argument("--asr", default="auto", choices=["auto", "faster-whisper", "none"])
    p.add_argument("--asr-model", default="small")
    p.add_argument("--re-asr", action="store_true", help="ignore cached transcript")
    p.add_argument("--language", default="vi")
    p.add_argument("--project")
    p.add_argument("--manifest", help="audited editor manifest; default = auto-detect this machine")
    p.add_argument("--platforms", default="tiktok,youtube-shorts,instagram-reels")
    p.add_argument("--intensity", choices=["subtle", "normal", "dynamic"])
    p.add_argument("--caption-style", choices=["clean-bold", "punchy-3", "boxed-calm"])
    p.add_argument("--music")
    p.add_argument("--music-license", choices=["own", "CC0", "licensed"])
    p.add_argument("--music-proof")
    p.add_argument("--sfx-library")
    p.add_argument("--vfx", action="store_true", help="enable the opt-in VFX skill")
    p.add_argument("--forbid", default="camera-shake", help="comma list, e.g. camera-shake,zoom")
    p.add_argument("--max-removed", type=float, default=0.35)
    p.add_argument("--max-revisions", type=int, default=2)
    p.add_argument("--fps", type=float)
    p.add_argument("--detect-faces", action="store_true")
    p.add_argument("--hook-title", default="auto", help='"auto" (keyword of the hook), "none", or your own text')
    p.add_argument("--cta", help="text of an end card, e.g. \"Theo dõi để xem phần 2\" (none by default)")
    p.add_argument("--no-progress-bar", action="store_true")
    p.add_argument("--no-callouts", action="store_true")
    p.add_argument("--llm", help="local Ollama model, e.g. qwen2.5:7b (optional)")
    p.add_argument("--no-beat-sync", action="store_true")
    p.add_argument("--no-publish", action="store_true", help="skip title/hashtag/cover kit")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--detach", action="store_true", help="run in background; poll with `status`")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("edit", help="edit one video")
    e.add_argument("input")
    _common(e)
    e.set_defaults(fn=cmd_edit)
    c = sub.add_parser("clips", help="long video -> several Shorts")
    c.add_argument("input")
    c.add_argument("--count", type=int, default=5)
    c.add_argument("--min-sec", type=float, default=20)
    c.add_argument("--max-sec", type=float, default=60)
    _common(c)
    c.set_defaults(fn=cmd_clips)
    st = sub.add_parser("story", help="script + voice + licensed scenes -> Short")
    st.add_argument("script")
    st.add_argument("--voice", help="your recorded voice (wav/mp3); default: TTS")
    st.add_argument("--voice-transcript", help="srt/json for --voice (else faster-whisper)")
    st.add_argument("--tts", default="piper", choices=["piper", "sapi", "espeak", "test"])
    st.add_argument("--tts-voice", help="piper model .onnx / SAPI voice name / espeak voice")
    st.add_argument("--tts-rate", type=float, default=1.0)
    st.add_argument("--library", action="append", help="folder of licensed clips (repeatable), e.g. from fetch_stock.py")
    st.add_argument("--fetch", action="store_true", help="download missing [scene:] clips from Pexels/Pixabay (API keys in env)")
    _common(st)
    st.set_defaults(fn=cmd_story)
    b = sub.add_parser("batch", help="edit every video in a folder (sidecar .srt/.json used if present)")
    b.add_argument("folder")
    b.add_argument("--redo", action="store_true")
    _common(b)
    b.set_defaults(fn=cmd_batch)
    s = sub.add_parser("status")
    s.add_argument("project")
    s.set_defaults(fn=cmd_status)
    cp = sub.add_parser("capabilities")
    cp.set_defaults(fn=cmd_capabilities)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
