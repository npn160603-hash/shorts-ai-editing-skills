import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib"), str(ROOT / "skills/04-smart-cut-pacing/lib")]
import pacing  # noqa: E402
import sae_testutil as U  # noqa: E402
import transitions as T  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

CL = load_json(ROOT / "skills/04-smart-cut-pacing/examples/cut-list.example.json")
TR = load_json(ROOT / "skills/04-smart-cut-pacing/examples/transcript.output-time.example.json")
DD = load_json(ROOT / "skills/01-editing-director/examples/director-decisions.example.json")
CAM = load_json(ROOT / "skills/03-camera-movement/examples/camera-track.example.json")
SPEECH = [(w["startSec"], w["endSec"]) for w in TR["words"]]


class TestTransitions(unittest.TestCase):
    def test_schema_and_reasons(self):
        tp = T.plan_transitions(CL, SPEECH, DD, CAM, max_visual=2, hook_end=DD["hookEndSec"])
        self.assertEqual(validate(tp, load_json(HERE / "schemas/transition-plan.schema.json")), [])
        self.assertTrue(all(t["reason"] for t in tp["transitions"]))

    def test_no_renderer_all_cuts(self):
        tp = T.plan_transitions(CL, SPEECH, DD, CAM, xfade_available=False)
        self.assertTrue(all(t["type"] == "cut" for t in tp["transitions"]))

    def test_budget_zero(self):
        tp = T.plan_transitions(CL, SPEECH, DD, None, max_visual=0)
        self.assertEqual(tp["visualCount"], 0)

    def test_needs_handles(self):
        cl = dict(CL, segments=[dict(s) for s in CL["segments"]])
        cl["segments"][2]["srcStartSec"] = cl["segments"][1]["srcEndSec"] + 0.02  # almost no removed gap
        tp = T.plan_transitions(cl, [], DD, None, max_visual=5, hook_end=0)
        b2 = next(t for t in tp["transitions"] if t["boundaryIndex"] == 2)
        self.assertEqual(b2["type"], "cut")
        self.assertIn("handle", b2["reason"])

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_duration_neutral_render(self):
        d = U.tmpdir()
        src = U.make_source(d / "src.mp4", 17.0)
        tp = {"transitionPlanVersion": "1.0", "timebase": "output", "visualCount": 1, "transitions": [
            {"boundaryIndex": 2, "atSec": 8.0667, "kind": "section", "type": "zoom", "xfade": "zoomin", "durationSec": 0.3,
             "handleSec": 0.86, "audio": "keep-cut", "reason": "test"}]}
        outs = {}
        for name, g in (("tr", T.ffmpeg_graph(CL, tp)), ("cut", pacing.ffmpeg_concat_filter(CL))):
            o = d / f"{name}.mp4"
            U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src), "-filter_complex", g, "-map", "[vout]", "-map", "[aout]",
                   "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(o)])
            outs[name] = {s["codec_type"]: s for s in U.probe(o)["streams"]}
        self.assertEqual(outs["tr"]["video"]["nb_read_frames"], outs["cut"]["video"]["nb_read_frames"])
        self.assertAlmostEqual(float(outs["tr"]["audio"]["duration"]), float(outs["cut"]["audio"]["duration"]), places=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
