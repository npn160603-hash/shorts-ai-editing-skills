import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator" / "lib"), str(ROOT / "core" / "lib")]
import conflicts as C  # noqa: E402
import runner as RN  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

S = ROOT / "skills"
DD = load_json(S / "01-editing-director/examples/director-decisions.example.json")
TP = load_json(S / "05-advanced-transitions/examples/transition-plan.example.json")
CAM = load_json(S / "03-camera-movement/examples/camera-track.example.json")
AM = load_json(S / "07-audio-director/examples/audio-mix-plan.example.json")
TR = load_json(S / "04-smart-cut-pacing/examples/transcript.output-time.example.json")


def fast_transcript(dur=8.0):
    text = ("Những thói quen buổi sáng đơn giản giúp bạn tập trung hiệu quả hơn mỗi ngày làm việc "
            "và tiết kiệm thời gian quý báu cho những dự định quan trọng nhất cuộc đời").split()
    ws, t, step = [], 0.3, (dur - 0.6) / len(text)
    for w in text:
        ws.append({"text": w, "startSec": round(t, 3), "endSec": round(t + step * 0.9, 3), "segmentId": "s1"})
        t += step
    return {"language": "vi", "timebase": "source", "wordTimestampsReliable": True, "producer": "test",
            "segments": [{"id": "s1", "text": " ".join(text), "startSec": 0.3, "endSec": round(t, 3)}], "words": ws}


class TestConflicts(unittest.TestCase):
    def test_transition_in_hook_downgraded_and_sfx_dropped(self):
        tp = copy.deepcopy(TP)
        tp["transitions"][1]["atSec"] = 1.0
        am = copy.deepcopy(AM)
        am["sfx"] = [{"id": "sfx01", "file": "w.wav", "category": "whoosh", "license": "own", "atSec": 0.9, "gainDb": -8,
                      "anchor": {"type": "transition", "ref": "2"}}]
        R, log = C.resolve({"transitionPlan": tp, "audioMixPlan": am, "transcript": TR, "directorDecisions": DD}, {"hookEndSec": 2.0})
        self.assertEqual(R["transitionPlan"]["transitions"][1]["type"], "cut")
        self.assertEqual(R["audioMixPlan"]["sfx"], [])
        self.assertEqual({e["rule"] for e in log} >= {"CR-03", "CR-07"}, True)

    def test_camera_overlap_dropped(self):
        cam = copy.deepcopy(CAM)
        m = dict(cam["moves"][0], id="m99", startSec=0.5)
        cam["moves"].append(m)
        R, log = C.resolve({"cameraTrack": cam}, {})
        self.assertNotIn("m99", [x["id"] for x in R["cameraTrack"]["moves"]])
        self.assertIn("CR-01", [e["rule"] for e in log])

    def test_overwrite_path_is_error(self):
        _, log = C.resolve({"cameraTrack": CAM}, {"outputPath": "/x/in.mp4", "sourcePath": "/x/in.mp4"})
        self.assertTrue(any(e["rule"] == "CR-10" and e["action"] == "error" for e in log))


class TestApplyFix(unittest.TestCase):
    def test_routes(self):
        P = RN._merge(RN.DEFAULT_PARAMS, {})
        f = {"suggestedFix": {"skill": "smart-captions", "action": "use-preset", "params": {"stylePreset": "punchy-3"}}}
        self.assertTrue(RN.apply_fix(P, f))
        self.assertEqual(P["captions"]["style"], "punchy-3")
        self.assertIsNone(RN.apply_fix(P, f))  # same fix twice -> no progress
        self.assertTrue(RN.apply_fix(P, {"suggestedFix": {"skill": "editing-director", "action": "tighten-budget", "params": {}}}))
        self.assertEqual(P["director"]["budgetScale"], 0.75)
        self.assertIsNone(RN.apply_fix(P, {"suggestedFix": {"skill": "ai-editing-orchestrator", "action": "fix-export-settings", "params": {}}}))


@unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
class TestRunnerEndToEnd(unittest.TestCase):
    def test_revise_loop_fixes_reading_speed(self):
        d = U.tmpdir()
        src = U.make_source(d / "src.mp4", 9.0)
        req = load_json(ROOT / "orchestrator/examples/edit-request.example.json")
        req["constraints"]["allowSfx"] = False
        man = load_json(ROOT / "core/examples/capability-manifest.demo-ffmpeg.json")
        reg = load_json(ROOT / "skills.registry.json")
        r = RN.Runner(req, man, reg, d / "proj")
        rep = r.run(str(src), fast_transcript())
        revs = rep["revisions"]
        self.assertGreaterEqual(len(revs), 2, rep)
        self.assertEqual(revs[0]["gate"], "fail")
        self.assertTrue(any(x["ruleId"] == "QA-CAP-01" for x in revs[0]["fixesApplied"]))
        self.assertEqual(revs[-1]["gate"], "pass", rep["needsHuman"])
        self.assertTrue(Path(rep["final"]["path"]).is_file())
        for e in revs:
            env = load_json(Path(e["dir"]) / "shorts-edit-plan.json")
            self.assertEqual(validate(env, load_json(ROOT / "core/schemas/shorts-edit-plan.schema.json")), [])
            self.assertTrue((Path(e["dir"]) / "contact_sheet.png").is_file())
        v = next(s for s in U.probe(Path(rep["final"]["path"]))["streams"] if s["codec_type"] == "video")
        self.assertEqual((v["width"], v["height"]), (1080, 1920))
        rep2 = RN.Runner(req, man, reg, d / "proj").run(str(src), fast_transcript(), export=False)
        self.assertGreater(rep2["revisions"][0]["revision"], revs[-1]["revision"])  # never overwrites
        self.assertTrue((d / "src.mp4").is_file())  # source untouched


if __name__ == "__main__":
    unittest.main(verbosity=2)
