"""AI Editing Runner — executes an OrchestrationPlan end-to-end with a QA-driven revise loop.

    plan  -> build sections (skills) -> conflict-check (CR-01..10) -> render preview
          -> QA (Skill 08) -> route suggestedFix to owner skills -> new revision ... -> export

Rendering goes through a *backend*. `FfmpegBackend` is the reference (verified with FFmpeg 6.1);
inside the real editor, Codex implements the same 4 methods on top of the editor's own pipeline
(`silence_log`, `render`, `measure_loudness`, `inspect`). Everything else is backend-independent.

Never overwrites: every iteration writes <project>/ai-edit/rev-<n>/ (new n each time).
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
for _p in ["core/lib", "orchestrator/lib", "tools"] + [f"skills/{d.name}/lib" for d in sorted((ROOT / "skills").iterdir()) if d.is_dir()]:
    if str(ROOT / _p) not in sys.path:
        sys.path.insert(0, str(ROOT / _p))

import audio_mix  # noqa: E402
import camera  # noqa: E402
import captions  # noqa: E402
import conflicts  # noqa: E402
import director  # noqa: E402
import orchestrate  # noqa: E402
import overlays  # noqa: E402
import pacing  # noqa: E402
import review  # noqa: E402
import sae_asr  # noqa: E402
import sae_layout  # noqa: E402
import sae_media  # noqa: E402
import transitions  # noqa: E402
import vfx  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

FONTS = ROOT / "core" / "fonts"
DEFAULT_PARAMS = {
    "cut": {"overrides": {}, "maxRemovedRatio": None},
    "director": {"budgetScale": 1.0},
    "captions": {"style": "clean-bold", "presetOverrides": {}, "platforms": ["tiktok", "youtube-shorts", "instagram-reels"]},
    "camera": {"zoomScale": 1.0},
    "transitions": {"forceCut": [], "maxVisual": None, "maxStyles": 2},
    "audio": {"music": True, "dropSfx": []},
    "overlays": {"hookTitle": "auto", "keywordCallouts": True, "progressBar": True, "cta": None},
    "detectSubjects": False,
    "llm": None,          # e.g. "qwen2.5:7b" via local Ollama (optional)
    "beatSync": True,     # snap keyword pops to the music beat when a confident beat is found
    "publish": True,      # write publish.json/.md + cover images next to the final video
}
OWNERS = {"cutList": "smart-cut-pacing", "transcript": "smart-cut-pacing", "contentAnalysis": "editing-director",
          "directorDecisions": "editing-director", "captionTrack": "smart-captions", "cameraTrack": "camera-movement",
          "transitionPlan": "advanced-transitions", "vfxPlan": "cinematic-vfx", "audioMixPlan": "audio-director",
          "motionPlan": "shorts-motion-designer"}
FILES = {"cutList": "cut-list.json", "transcript": "transcript.output-time.json", "contentAnalysis": "content-analysis.json",
         "directorDecisions": "director-decisions.json", "captionTrack": "caption-track.json", "cameraTrack": "camera-track.json",
         "transitionPlan": "transition-plan.json", "vfxPlan": "vfx-plan.json", "audioMixPlan": "audio-mix-plan.json",
         "motionPlan": "motion-plan.v1_0.json"}


def _dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _merge(a: Dict, b: Dict) -> Dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


# ====================================================================== backend (reference)
class FfmpegBackend:
    name = "ffmpeg-reference"

    def __init__(self, preview_crf: int = 26, final_crf: int = 18, preview_scale: float = 0.5):
        self.preview_crf, self.final_crf = preview_crf, final_crf
        self.preview_scale = preview_scale  # previews are rendered smaller (faster); export is full size

    def preview_size(self, out: Dict) -> Dict:
        w = int(round(out["width"] * self.preview_scale / 2) * 2)
        h = int(round(out["height"] * self.preview_scale / 2) * 2)
        return {"width": w, "height": h, "fps": out["fps"]}

    @staticmethod
    def _run(cmd: List[str]) -> subprocess.CompletedProcess:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError("FFmpeg failed: " + " ".join(cmd)[:300] + "\n" + r.stderr[-1500:])
        return r

    def silence_log(self, src: str) -> str:
        return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-af", "silencedetect=noise=-35dB:d=0.25",
                               "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr

    def render(self, src: str, S: Dict, out_dir: Path, final: bool, has_audio: bool, assets: Dict[str, str]) -> Path:
        cut, tp, cam, fx, tk, am = (S.get(k) for k in ("cutList", "transitionPlan", "cameraTrack", "vfxPlan", "captionTrack", "audioMixPlan"))
        graph = transitions.ffmpeg_graph(cut, tp, has_audio) if tp else pacing.ffmpeg_concat_filter(cut, has_audio=has_audio)
        vchain = camera.ffmpeg_filter(cam)
        if fx and fx["items"]:
            vchain += "," + vfx.ffmpeg_chain(fx)
        if tk and tk["pages"]:
            ass = out_dir / "captions.ass"
            txt = captions.to_ass(tk, S.get("_captionPresets"))
            ov = S.get("_overlays")
            if ov is not None:
                styles, events, used = overlays.overlay_events(tk, S.get("directorDecisions"), cut["stats"]["outputDurationSec"],
                                                               ov, S.get("_captionPresets"))
                txt = overlays.merge_into_ass(txt, styles, events)
                S["_overlaysUsed"] = used
            ass.write_text(txt, encoding="utf-8")
            vchain += "," + captions.ffmpeg_subtitles_filter(str(ass), str(FONTS))
        if not final and self.preview_scale != 1.0:
            ps = self.preview_size({"width": cam["output"]["width"], "height": cam["output"]["height"], "fps": 30})
            vchain += f",scale={ps['width']}:{ps['height']}:flags=bilinear"
        graph += f";[vout]{vchain}[vfinal]"
        stage = out_dir / ("_stage_final.mp4" if final else "_stage_preview.mp4")
        crf, preset = (self.final_crf, "veryfast") if final else (self.preview_crf, "ultrafast")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", src, "-filter_complex", graph, "-map", "[vfinal]"]
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"] if has_audio else []
        self._run(cmd + ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", str(stage)])
        out = out_dir / ("final.mp4" if final else "preview.mp4")
        if not has_audio or not am:
            stage.rename(out)
            return out
        inputs = ["-i", str(stage)]
        music = am.get("music")
        if music:
            inputs += ["-stream_loop", "-1", "-i", assets.get(music["file"], music["file"])]
        sfx_first = 2 if music else 1
        for e in am.get("sfx", []):
            inputs += ["-i", assets.get(e["file"], e["file"])]
        premix = out_dir / "_premix.wav"
        g0 = audio_mix.ffmpeg_mix_graph(am, None, music_input=1, sfx_first_input=sfx_first)
        self._run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", *inputs, "-filter_complex", g0, "-map", "[amix]",
                   "-t", f"{am['durationSec']}", str(premix)])
        measured = self.measure_loudness(str(premix), am["targets"]) if am["voice"]["loudnorm"] == "two-pass" else None
        g1 = audio_mix.ffmpeg_mix_graph(am, measured, music_input=1, sfx_first_input=sfx_first)
        self._run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", *inputs, "-filter_complex", g1, "-map", "0:v", "-map", "[amix]",
                   "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{am['durationSec']}", str(out)])
        stage.unlink(missing_ok=True)
        premix.unlink(missing_ok=True)
        return out

    def measure_loudness(self, path: str, targets: Dict) -> Dict:
        r = subprocess.run(audio_mix.measure_cmd(path, targets), capture_output=True, text=True, encoding="utf-8", errors="replace")
        return audio_mix.parse_loudnorm_json(r.stderr)

    def inspect(self, path: str) -> Dict:
        cmds = review.detect_cmds(path)
        probe = json.loads(self._run(cmds["probe"]).stdout)
        logs = {k: subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
                for k, c in cmds.items() if k != "probe"}
        return {"probe": probe, "logs": logs}

    def contact_sheet(self, path: str, png: Path) -> None:
        self._run(review.contact_sheet_cmd(path, str(png)))


# ====================================================================== fix routing
def apply_fix(params: Dict, finding: Dict) -> Optional[str]:
    """Translate a QA suggestedFix into a parameter change. Returns a description, or None
    when the fix cannot be automated (-> needs a human)."""
    fx = finding.get("suggestedFix")
    if not fx:
        return None
    sk, act, pa = fx["skill"], fx["action"], fx.get("params", {})
    c = params["captions"]
    if sk == "smart-captions":
        if act == "use-preset" and c["style"] != pa.get("stylePreset"):
            c["style"] = pa["stylePreset"]
            return f"captions.style -> {c['style']}"
        if act == "set":
            c["presetOverrides"].update(pa)
            return f"captions overrides {pa}"
        if act == "merge-short-pages":
            o = c["presetOverrides"]
            o["minPageSec"] = round(o.get("minPageSec", 0.5) + 0.15, 2)
            return f"captions.minPageSec -> {o['minPageSec']}"
        if act == "re-place":
            o = c["presetOverrides"]
            cands = o.get("placementCandidatesY", [0.70, 0.32, 0.80])
            o["placementCandidatesY"] = cands[1:] + cands[:1]
            return f"captions placement order -> {o['placementCandidatesY']}"
        return None
    if sk == "editing-director" and act == "tighten-budget":
        params["director"]["budgetScale"] = round(params["director"]["budgetScale"] * 0.75, 3)
        return f"director.budgetScale -> {params['director']['budgetScale']}"
    if sk == "advanced-transitions":
        t = params["transitions"]
        if act == "downgrade-to-cut" and pa.get("boundaryIndex") not in t["forceCut"]:
            t["forceCut"].append(pa["boundaryIndex"])
            return f"transition {pa['boundaryIndex']} forced to cut"
        if act == "replan":
            t["maxVisual"] = pa.get("maxVisual", 0)
            return f"transitions.maxVisual -> {t['maxVisual']}"
        if act == "limit-styles":
            t["maxStyles"] = pa.get("max", 2)
            return f"transitions.maxStyles -> {t['maxStyles']}"
        return None
    if sk == "camera-movement" and act == "cap-zoom":
        params["camera"]["zoomScale"] = round(params["camera"]["zoomScale"] * 0.8, 3)
        return f"camera.zoomScale -> {params['camera']['zoomScale']}"
    if sk == "smart-cut-pacing":
        o = params["cut"]["overrides"]
        if act == "raise":
            o.update(pa)
            return f"cut overrides {pa}"
        if act == "trim-head":
            o["edgePadSec"] = 0.05
            return "cut.edgePadSec -> 0.05"
        if act == "rebuild" and "maxRemovedRatio" in pa:
            params["cut"]["maxRemovedRatio"] = pa["maxRemovedRatio"]
            return f"cut.maxRemovedRatio -> {pa['maxRemovedRatio']}"
        return None
    if sk == "audio-director":
        if act == "remove-music" and params["audio"]["music"]:
            params["audio"]["music"] = False
            return "music removed"
        if act == "remove-sfx" and pa.get("id") not in params["audio"]["dropSfx"]:
            params["audio"]["dropSfx"].append(pa["id"])
            return f"sfx {pa['id']} removed"
        return None
    return None


# ====================================================================== runner
class Runner:
    def __init__(self, request: Dict, manifest: Dict, registry: Dict, project_dir, backend=None,
                 assets: Optional[Dict[str, str]] = None, sfx_library: Optional[Dict] = None, progress=None):
        self.request, self.manifest, self.registry = request, manifest, registry
        self.project = Path(project_dir)
        self.backend = backend or FfmpegBackend()
        self.assets = assets or {}
        self.sfx_library = sfx_library
        self.caps = {k: v["status"] for k, v in manifest["capabilities"].items()}
        self.orch = orchestrate.plan(request, manifest, registry)
        self.status = {s["id"]: s for s in self.orch["skills"]}
        self.out = manifest["output"]
        self.progress = progress or (lambda stage, **kw: None)  # progress(stage, **details)

    def active(self, sid: str) -> bool:
        return self.status.get(sid, {}).get("status") in ("planned", "fallback")

    def mode(self, sid: str) -> str:
        return self.status.get(sid, {}).get("mode", "")

    # ------------------------------------------------------------ sections
    def build_sections(self, src: Dict, transcript: Dict, params: Dict, silence_log: Optional[str] = None,
                       subject_boxes_src: Optional[Dict] = None) -> Dict:
        P = _merge(DEFAULT_PARAMS, params)
        cons = self.request.get("constraints", {})
        intensity = self.orch["intensity"]
        budget = self.orch["effectBudget"]
        fps = self.out["fps"]
        dur = src["durationSec"]
        S: Dict = {}
        if self.active("smart-cut-pacing"):
            log = silence_log if "silence-signal" in self.mode("smart-cut-pacing") else None
            S["cutList"] = pacing.plan_cuts(transcript, dur, fps, intensity,
                                            P["cut"]["maxRemovedRatio"] or cons.get("maxRemovedRatio", 0.35),
                                            silence_log=log, overrides=P["cut"]["overrides"])
        else:
            n = int(round(dur * fps))
            S["cutList"] = {"cutListVersion": "1.0", "timebase": "source", "sourceDurationSec": dur, "fps": fps,
                            "segments": [{"id": "k001", "srcStartSec": 0.0, "srcEndSec": round(n / fps, 4), "outStartSec": 0.0}],
                            "removed": [], "rejected": [],
                            "stats": {"removedSec": 0.0, "removedRatio": 0.0, "outputDurationSec": round(n / fps, 4), "cutCount": 0}}
        cut = S["cutList"]
        tr = pacing.remap_transcript(transcript, cut)
        S["transcript"] = tr
        odur = cut["stats"]["outputDurationSec"]
        cuts_out = [s["outStartSec"] for s in cut["segments"][1:]]
        boxes = []
        if subject_boxes_src:
            import subject_boxes
            boxes = subject_boxes.remap_to_output(subject_boxes_src, cut)["boxes"]
        S["_subjectBoxes"] = boxes
        dd = None
        overrides = None
        if P.get("llm") and self.active("editing-director"):
            try:
                import sae_llm
                overrides = sae_llm.segment_overrides(P["llm"], tr["segments"])
                self.progress("llm", task="segment roles/keywords", segments=len(overrides))
            except Exception as e:  # noqa: BLE001  (LLM is optional: fall back to heuristics)
                self.progress("llm", task="segment roles/keywords", error=str(e)[:200])
        if self.active("editing-director"):
            b = {k: (v * P["director"]["budgetScale"] if k in ("maxAccentsPer10s", "maxCameraMovesPer10s") else v) for k, v in budget.items()}
            S["contentAnalysis"] = director.analyze(tr, odur, ai_overrides=overrides)
            dd = S["directorDecisions"] = director.decide(S["contentAnalysis"], intensity, b, cuts_out, tr.get("words", []),
                                                          allow_camera=self.active("camera-movement"))
        safe = sae_layout.safe_area_for(P["captions"]["platforms"])
        if self.active("smart-captions"):
            presets = captions.load_presets()
            st = P["captions"]["style"]
            presets[st] = dict(presets[st], **P["captions"]["presetOverrides"])
            S["captionTrack"] = captions.build_track(tr, {"width": self.out["width"], "height": self.out["height"]}, safe, st, dd,
                                                     boxes, presets=presets, force_phrase=self.mode("smart-captions").startswith("phrase"),
                                                     duration=odur)
            S["_captionPresets"] = presets
        cam_mode = self.mode("camera-movement") if self.active("camera-movement") else "center-weighted"
        shake = "no-shake" not in cam_mode and intensity == "dynamic"
        S["cameraTrack"] = camera.build_track(dd if (dd and self.active("camera-movement")) else {"accents": []},
                                              {"width": src["width"], "height": src["height"]}, self.out, cam_mode, boxes, cuts_out,
                                              allow_shake=shake, zoom_scale=P["camera"]["zoomScale"])
        speech = [(w["startSec"], w["endSec"]) for w in tr.get("words", [])] or [(s["startSec"], s["endSec"]) for s in tr["segments"]]
        if len(cut["segments"]) > 1:
            S["transitionPlan"] = transitions.plan_transitions(
                cut, speech, dd, S["cameraTrack"],
                max_visual=P["transitions"]["maxVisual"] if P["transitions"]["maxVisual"] is not None else budget["maxVisualTransitions"],
                xfade_available=self.active("advanced-transitions") and self.mode("advanced-transitions") == "restrained",
                hook_end=dd["hookEndSec"] if dd else 2.0, forbidden=cons.get("forbiddenEffects", []),
                force_cut=P["transitions"]["forceCut"], max_styles=P["transitions"]["maxStyles"])
        if self.active("cinematic-vfx") and dd:
            S["vfxPlan"] = vfx.plan_vfx(dd, self.caps, intensity, duration=odur,
                                        hardware_budget=self.manifest.get("hardware", {}).get("maxRenderSecondsPerOutputSecond"),
                                        forbidden=cons.get("forbiddenEffects", []))
        if self.active("audio-director"):
            music = None
            if P["audio"]["music"] and cons.get("allowMusic") and cons.get("musicFile"):
                music = {"file": cons["musicFile"], "license": cons.get("musicLicense", ""), "licenseProof": cons.get("musicLicenseProof", "")}
            anchors = [{"type": "transition", "atSec": t["atSec"], "ref": str(t["boundaryIndex"])}
                       for t in (S.get("transitionPlan") or {}).get("transitions", []) if t["type"] != "cut"]
            anchors += [{"type": a["type"], "atSec": a["atSec"], "ref": a.get("target", "")}
                        for a in (dd or {}).get("accents", []) if a["type"] in ("keyword-pop", "callout")]
            caps = dict(self.caps)
            if not cons.get("allowSfx"):
                caps["audio.mixSfx"] = "missing"
            am = audio_mix.build_plan(odur, speech, caps, speech_priority=self.orch["resolvedIntent"].get("speechPriority", True),
                                      music=music, sfx_lib=self.sfx_library, anchors=anchors, max_sfx_per_10s=budget["maxSfxPer10s"])
            am["sfx"] = [e for e in am["sfx"] if e["id"] not in P["audio"]["dropSfx"]]
            if am.get("music") and P.get("beatSync") and dd:
                grid = self._beat_grid(self.assets.get(am["music"]["file"], am["music"]["file"]), odur)
                if grid:
                    am["beatGrid"] = {"bpm": grid["bpm"], "offsetSec": grid["offsetSec"], "confidence": grid["confidence"],
                                      "method": "onset-autocorrelation"}
                    words_out = tr.get("words", [])
                    for a in dd["accents"]:
                        if a["type"] not in ("keyword-pop", "callout"):
                            continue
                        nb = min(grid["beats"], key=lambda t: abs(t - a["atSec"]), default=None)
                        if nb is None or abs(nb - a["atSec"]) > 0.12:
                            continue
                        w = next((w for w in words_out if w["startSec"] - 0.01 <= a["atSec"] <= w["endSec"]), None)
                        if w is None or abs(nb - w["startSec"]) <= 0.08:
                            a["atSec"], a["beatSnapped"] = round(nb, 3), True
            S["audioMixPlan"] = am
        if S.get("captionTrack") and self.active("shorts-motion-designer"):
            kws = [a for a in (dd or {}).get("accents", []) if a["type"] == "keyword-pop"]
            S["motionPlan"] = captions.to_motion_plan(S["captionTrack"], fps, odur, presets=S.get("_captionPresets"), keyword_callouts=kws)
        if P.get("overlays") is not None and S.get("captionTrack"):
            S["_overlays"] = P["overlays"]
            if P["overlays"].get("hookTitle") and S["captionTrack"]["pages"]:
                # hook title owns the top of the frame during the hook -> keep hook captions low
                for pg in S["captionTrack"]["pages"]:
                    if pg["captionMode"] == "headline" and pg["placement"]["y"] < 0.5 and dd:
                        title = overlays._hook_title(dd, P["overlays"]["hookTitle"])
                        if title:
                            pg["placement"]["y"] = round(min(0.70, 1 - safe["bottom"] - pg["placement"].get("blockHeight", 0.1) / 2), 4)
        S["_params"] = P
        return S

    # ------------------------------------------------------------ helpers
    def _beat_grid(self, music_path: str, duration: float) -> Optional[Dict]:
        """BPM + beat times of the music (heuristic DSP, first 30 s). None if not confident."""
        if not hasattr(self, "_beat_cache"):
            self._beat_cache = {}
        if music_path in self._beat_cache:
            return self._beat_cache[music_path]
        res = None
        try:
            raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-t", "30", "-i", music_path, "-ac", "1", "-ar", "11025",
                                  "-f", "s16le", "-"], capture_output=True, check=True).stdout
            import array
            arr = array.array("h")
            arr.frombytes(raw[: len(raw) // 2 * 2])
            if sys.byteorder == "big":
                arr.byteswap()
            bpm, off, conf = audio_mix.estimate_bpm([x / 32768 for x in arr], 11025)
            if bpm and conf >= 0.3:
                res = {"bpm": bpm, "offsetSec": off, "confidence": conf, "beats": audio_mix.beat_grid(bpm, off, duration)}
        except Exception:  # noqa: BLE001
            res = None
        self._beat_cache[music_path] = res
        return res


    def _next_rev(self) -> Path:
        base = self.project / "ai-edit"
        base.mkdir(parents=True, exist_ok=True)
        n = 1
        while (base / f"rev-{n}").exists():
            n += 1
        d = base / f"rev-{n}"
        d.mkdir()
        return d

    def _envelope(self, rev_dir: Path, rev: int, parent: int, src: Dict, src_path: str, S: Dict, history: List[Dict]) -> Dict:
        secs = {}
        for name, owner in OWNERS.items():
            if S.get(name) is not None:
                secs[name] = {"ownerSkill": owner, "status": "fallback" if self.status.get(owner, {}).get("status") == "fallback" else "ready",
                              "timebase": "output", "file": FILES[name]}
            else:
                st = self.status.get(owner, {})
                secs[name] = {"ownerSkill": owner, "status": "skipped", "timebase": "output",
                              "reason": "; ".join(st.get("reasons", ["not produced"]))[:200]}
        secs["cutList"]["timebase"] = "source"
        secs["qaReport"] = {"ownerSkill": "visual-quality-reviewer", "status": "pending", "timebase": "output", "file": "qa-report.json"}
        env = {"planVersion": "1.0", "revision": rev, "parentRevision": parent,
               "source": {"path": src_path, "durationSec": src["durationSec"], "fps": src["avgFrameRate"] or self.out["fps"],
                          "width": src["width"], "height": src["height"]},
               "output": {"width": self.out["width"], "height": self.out["height"], "fps": self.out["fps"],
                          "pathTemplate": str(self.project / "ai-edit" / "rev-{revision}" / "final.mp4")},
               "intensity": self.orch["intensity"], "sections": secs, "history": history}
        errs = validate(env, load_json(ROOT / "core/schemas/shorts-edit-plan.schema.json"))
        if errs:
            raise RuntimeError("ShortsEditPlan invalid: " + "; ".join(errs[:5]))
        return env

    # ------------------------------------------------------------ main loop
    def run(self, source: str, transcript, params: Optional[Dict] = None, subject_boxes: Optional[Dict] = None,
            export: bool = True) -> Dict:
        source = str(source)
        if isinstance(transcript, (str, Path)):
            transcript = sae_asr.strict(sae_asr.load_any(transcript, self.request.get("language", "vi")))
        report: Dict = {"runnerVersion": "1.0", "backend": self.backend.name, "source": source, "orchestration": self.orch,
                        "revisions": [], "needsHuman": []}
        first = self._next_rev()
        src_path = source
        v = sae_media.is_vfr(source)
        if v["vfr"]:
            self.progress("normalize-vfr", reasons=v["reasons"])
            src_path = str(first / "source_cfr.mp4")
            subprocess.run(sae_media.normalize_cmd(source, src_path, fps=self.out["fps"]), check=True, capture_output=True)
            report["normalized"] = {"from": source, "to": src_path, "reasons": v["reasons"]}
        src = sae_media.probe_media(src_path)
        P = _merge(DEFAULT_PARAMS, params or {})
        if P.get("detectSubjects") and subject_boxes is None:
            import subject_boxes as SB
            if SB.available():
                try:
                    subject_boxes = SB.detect(src_path)
                except RuntimeError as e:
                    report["needsHuman"].append(f"subject detection unavailable: {e}")
        self.progress("analyze", source=src_path, durationSec=src["durationSec"])
        silence = self.backend.silence_log(src_path) if self.caps.get("analysis.silenceDetect") == "implemented" else None
        max_iter = self.orch["reviewLoop"]["maxIterations"]
        history: List[Dict] = []
        prev_fp = None
        rev_dir, parent = first, 0
        for it in range(max_iter + 1):
            rev = int(rev_dir.name.split("-")[1])
            self.progress("build-sections", revision=rev)
            S = self.build_sections(src, transcript, P, silence, subject_boxes)
            ctx = {"hookEndSec": (S.get("directorDecisions") or {}).get("hookEndSec", 2.0), "effectBudget": self.orch["effectBudget"],
                   "subjectBoxes": S["_subjectBoxes"], "owners": OWNERS, "producedBy": dict(OWNERS),
                   "outputPath": str(rev_dir / "preview.mp4"), "sourcePath": source}
            R, clog = conflicts.resolve(S, ctx)
            for name, fn in FILES.items():
                if R.get(name) is not None:
                    _dump(R[name], rev_dir / fn)
            _dump({"params": R["_params"], "conflictLog": clog}, rev_dir / "run-params.json")
            if any(e["action"] == "error" for e in clog):
                report["needsHuman"].append(f"rev-{rev}: conflict-check errors {[e for e in clog if e['action'] == 'error']}")
                break
            has_audio = src["hasAudio"]
            self.progress("render-preview", revision=rev)
            preview = self.backend.render(src_path, R, rev_dir, final=False, has_audio=has_audio, assets=self.assets)
            insp = self.backend.inspect(str(preview))
            meas = self.backend.measure_loudness(str(preview), R["audioMixPlan"]["targets"]) if (has_audio and R.get("audioMixPlan")) else None
            rr = review.Report()
            presets = R.get("_captionPresets") or {}
            if R.get("captionTrack"):
                review.check_captions(rr, R["captionTrack"], R["transcript"], R["cutList"]["stats"]["outputDurationSec"], R["_subjectBoxes"],
                                      max_cps=presets.get(R["captionTrack"]["stylePreset"], {}).get("maxCps", 17))
            review.check_pacing(rr, R["cutList"], R.get("directorDecisions"), R["transcript"], self.orch["effectBudget"],
                                self.request.get("constraints", {}).get("maxRemovedRatio", 0.35))
            review.check_transitions(rr, R.get("transitionPlan"), ctx["hookEndSec"], self.orch["effectBudget"]["maxVisualTransitions"])
            review.check_camera(rr, R.get("cameraTrack"))
            review.check_audio(rr, R.get("audioMixPlan"), meas)
            expected = self.backend.preview_size(self.out) if hasattr(self.backend, "preview_size") else self.out
            review.check_render(rr, insp["probe"], expected, insp["logs"], str(preview), source)
            qa = review.finalize(rr, rev)
            self.progress("qa", revision=rev, gate=qa["gate"], counts=qa["counts"])
            _dump(qa, rev_dir / "qa-report.json")
            self.backend.contact_sheet(str(preview), rev_dir / "contact_sheet.png")
            entry = {"revision": rev, "dir": str(rev_dir), "gate": qa["gate"], "counts": qa["counts"], "conflictLog": clog, "fixesApplied": []}
            fixable = [f for f in qa["findings"] if f["severity"] in ("blocker", "major")]
            fp = sorted((f["ruleId"], json.dumps(f["evidence"], sort_keys=True)) for f in fixable)
            stop = qa["gate"] == "pass" or it == max_iter or fp == prev_fp
            if not stop:
                for f in fixable:
                    d = apply_fix(P, f)
                    if d:
                        entry["fixesApplied"].append({"finding": f["id"], "ruleId": f["ruleId"], "change": d})
                    else:
                        report["needsHuman"].append(f"rev-{rev} {f['ruleId']}: {f['message']} {f['evidence']}")
                if not entry["fixesApplied"]:
                    stop = True
            if entry["fixesApplied"]:
                self.progress("revise", revision=rev, fixes=[f["change"] for f in entry["fixesApplied"]])
            history.append({"revision": rev, "note": f"gate={qa['gate']} fixes={len(entry['fixesApplied'])}"})
            env = self._envelope(rev_dir, rev, parent, src, src_path, R, history)
            env["sections"]["qaReport"]["status"] = "ready"
            _dump(env, rev_dir / "shorts-edit-plan.json")
            report["revisions"].append(entry)
            prev_fp = fp
            if stop:
                if qa["gate"] == "fail":
                    report["needsHuman"] += [f"rev-{rev} {f['ruleId']}: {f['message']}" for f in fixable
                                             if not any(x.endswith(f"{f['ruleId']}: {f['message']}") for x in report["needsHuman"])]
                break
            parent, rev_dir = rev, self._next_rev()
        last = report["revisions"][-1]
        final_path = None
        approval = self.request.get("constraints", {}).get("requireApprovalBeforeExport", False)
        if export and not approval:
            self.progress("export", revision=last["revision"])
            final_path = str(self.backend.render(src_path, R, Path(last["dir"]), final=True, has_audio=src["hasAudio"], assets=self.assets))
        report["final"] = {"revision": last["revision"], "gate": last["gate"], "path": final_path,
                           "awaitingApproval": bool(export and approval)}
        if final_path and P.get("publish"):
            try:
                import publish
                llm_titles = []
                if P.get("llm"):
                    try:
                        import sae_llm
                        llm_titles = sae_llm.title_ideas(P["llm"], " ".join(x["text"] for x in R["transcript"]["segments"]))
                    except Exception:  # noqa: BLE001
                        llm_titles = []
                kit = publish.suggest(R["transcript"], R.get("directorDecisions"), P["captions"]["platforms"], llm_titles,
                                      params.get("credits") if params else None)
                # cover from the clean source (no captions/overlays), first seconds = the hook
                kit["cover"] = publish.make_cover(src_path, kit["titles"][0] if kit["titles"] else "", Path(last["dir"]))
                report["final"]["publishKit"] = str(publish.write_kit(Path(last["dir"]), kit))
                self.progress("publish-kit", path=report["final"]["publishKit"])
            except Exception as e:  # noqa: BLE001
                report["needsHuman"].append(f"publish kit failed: {e}")
        _dump(report, Path(last["dir"]) / "run-report.json")
        self.progress("done", final=final_path, gate=last["gate"], report=str(Path(last["dir"]) / "run-report.json"))
        return report
