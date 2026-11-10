"""End-to-end demo on the bundled fixtures, using the real Runner (stdlib + FFmpeg only).

  python scripts/run_pipeline_demo.py                  # plan-only: every section JSON, no render
  python scripts/run_pipeline_demo.py --render         # synthetic 9:16 clip -> Runner (preview, QA, revise, export)
  python scripts/run_pipeline_demo.py --write-examples # maintainers: refresh examples/ in every skill

Outputs go to _demo_out/ai-edit/rev-<n>/ (never overwritten).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator" / "lib"))
import runner as RN  # noqa: E402  (also puts core/skills libs on sys.path)
import camera  # noqa: E402
import captions  # noqa: E402
import director  # noqa: E402
import review  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

SRC_DUR = 17.0
FACE = {"subjectBoxesVersion": "1.0", "timebase": "source", "detector": "fixture",
        "boxes": [{"startSec": 6.5, "endSec": 9.5, "box": {"x": 0.3, "y": 0.55, "w": 0.4, "h": 0.25}, "label": "face"}]}
SCHEMAS = {"cutList": "skills/04-smart-cut-pacing/schemas/cut-list.schema.json",
           "transcript": "core/schemas/transcript.schema.json",
           "contentAnalysis": "skills/01-editing-director/schemas/content-analysis.schema.json",
           "directorDecisions": "skills/01-editing-director/schemas/director-decisions.schema.json",
           "captionTrack": "skills/02-smart-captions/schemas/caption-track.schema.json",
           "cameraTrack": "skills/03-camera-movement/schemas/camera-track.schema.json",
           "transitionPlan": "skills/05-advanced-transitions/schemas/transition-plan.schema.json",
           "vfxPlan": "skills/06-cinematic-vfx/schemas/vfx-plan.schema.json",
           "audioMixPlan": "skills/07-audio-director/schemas/audio-mix-plan.schema.json"}


def setup(enable_vfx: bool = True):
    req = load_json(ROOT / "orchestrator/examples/edit-request.example.json")
    req["constraints"].update(allowMusic=True, musicFile="assets/music/bed-own-01.wav", musicLicense="own",
                              musicLicenseProof="synthesised by run_pipeline_demo.py")
    req["intent"] = {"vfx": enable_vfx, "music": True, "sfx": True}
    man = load_json(ROOT / "core/examples/capability-manifest.demo-ffmpeg.json")
    reg = load_json(ROOT / "skills.registry.json")
    for s in reg["skills"]:
        if s["id"] == "cinematic-vfx":
            s["enabled"] = enable_vfx
    lib = load_json(ROOT / "skills/07-audio-director/examples/sfx-library.example.json")
    return req, man, reg, lib


def plan_only(out: Path) -> dict:
    req, man, reg, lib = setup()
    r = RN.Runner(req, man, reg, out, sfx_library=lib)
    src = {"width": 1080, "height": 1920, "durationSec": SRC_DUR, "avgFrameRate": 30.0, "hasAudio": True}
    tr = load_json(ROOT / "core/examples/transcript.example.json")
    log = (ROOT / "skills/04-smart-cut-pacing/examples/silencedetect.log.txt").read_text(encoding="utf-8")
    S = r.build_sections(src, tr, {}, log, FACE)
    for k, sch in SCHEMAS.items():
        if S.get(k) is not None:
            errs = validate(S[k], load_json(ROOT / sch))
            if errs:
                raise SystemExit(f"{k} invalid: {errs[:5]}")
    rr = review.Report()
    review.check_captions(rr, S["captionTrack"], S["transcript"], S["cutList"]["stats"]["outputDurationSec"], S["_subjectBoxes"])
    review.check_pacing(rr, S["cutList"], S["directorDecisions"], S["transcript"], r.orch["effectBudget"])
    review.check_transitions(rr, S.get("transitionPlan"), S["directorDecisions"]["hookEndSec"], r.orch["effectBudget"]["maxVisualTransitions"])
    review.check_camera(rr, S["cameraTrack"])
    review.check_audio(rr, S["audioMixPlan"], None)
    S["qaReport"] = review.finalize(rr, 1)
    S["orchestration"] = r.orch
    return S


def synth_assets(d: Path) -> dict:
    d.mkdir(parents=True, exist_ok=True)
    jobs = {"music.wav": ("sine=f=330:d=20", "volume='0.3+0.7*lt(mod(t,0.5),0.06)':eval=frame"),
            "whoosh.wav": ("anoisesrc=d=0.45:c=pink:a=0.5", "afade=t=in:d=0.2,afade=t=out:st=0.25:d=0.2"),
            "pop.wav": ("sine=f=900:d=0.12", "afade=t=out:st=0.04:d=0.08"),
            "tick.wav": ("sine=f=1800:d=0.08", "afade=t=out:st=0.02:d=0.06")}
    for name, (src, af) in jobs.items():
        if not (d / name).exists():
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", src, "-af", af, str(d / name)], check=True)
    if not (d / "source.mp4").exists():
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate=30:duration={SRC_DUR}",
                        "-f", "lavfi", "-i", f"sine=frequency=220:duration={SRC_DUR}", "-af", "volume='0.25+0.6*lt(mod(t,0.8),0.4)':eval=frame",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "source.mp4")], check=True)
    return {"assets/music/bed-own-01.wav": str(d / "music.wav"), "assets/sfx/whoosh-soft-01.wav": str(d / "whoosh.wav"),
            "assets/sfx/pop-01.wav": str(d / "pop.wav"), "assets/sfx/tick-01.wav": str(d / "tick.wav")}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--write-examples", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "_demo_out"))
    a = ap.parse_args()
    out = Path(a.out)
    S = plan_only(out)
    print(f"plan OK — QA (plan-level): gate={S['qaReport']['gate']} counts={S['qaReport']['counts']}")
    if a.write_examples:
        X = ROOT / "skills"
        RN._dump(S["orchestration"], ROOT / "orchestrator/examples/orchestration-plan.demo-ffmpeg.example.json")
        for k, rel in [("cutList", "04-smart-cut-pacing/examples/cut-list.example.json"),
                       ("transcript", "04-smart-cut-pacing/examples/transcript.output-time.example.json"),
                       ("contentAnalysis", "01-editing-director/examples/content-analysis.example.json"),
                       ("directorDecisions", "01-editing-director/examples/director-decisions.example.json"),
                       ("captionTrack", "02-smart-captions/examples/caption-track.example.json"),
                       ("motionPlan", "02-smart-captions/examples/motion-plan.compiled.example.json"),
                       ("cameraTrack", "03-camera-movement/examples/camera-track.example.json"),
                       ("transitionPlan", "05-advanced-transitions/examples/transition-plan.example.json"),
                       ("vfxPlan", "06-cinematic-vfx/examples/vfx-plan.example.json"),
                       ("audioMixPlan", "07-audio-director/examples/audio-mix-plan.example.json"),
                       ("qaReport", "08-visual-quality-reviewer/examples/qa-report.example.json")]:
            RN._dump(S[k], X / rel)
        (X / "02-smart-captions/examples/captions.example.ass").write_text(captions.to_ass(S["captionTrack"]), encoding="utf-8")
        (X / "03-camera-movement/examples/camera.ffmpeg-filter.txt").write_text(camera.ffmpeg_filter(S["cameraTrack"]) + "\n", encoding="utf-8")
        print("examples refreshed")
    if a.render:
        req, man, reg, lib = setup()
        assets = synth_assets(out / "_synthetic")
        tr = load_json(ROOT / "core/examples/transcript.example.json")
        rep = RN.Runner(req, man, reg, out, assets=assets, sfx_library=lib).run(str(out / "_synthetic/source.mp4"), tr, subject_boxes=FACE)
        for e in rep["revisions"]:
            print(f"rev-{e['revision']}: gate={e['gate']} counts={e['counts']} fixes={[f['change'] for f in e['fixesApplied']]} "
                  f"conflicts={[c['rule'] + ':' + c['action'] for c in e['conflictLog']]}")
        print("final:", rep["final"])
        if rep["needsHuman"]:
            print("needs human:", *rep["needsHuman"], sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
