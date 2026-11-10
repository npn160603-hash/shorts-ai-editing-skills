import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib")]
import review as R  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

S = ROOT / "skills"
TK = load_json(S / "02-smart-captions/examples/caption-track.example.json")
TR = load_json(S / "04-smart-cut-pacing/examples/transcript.output-time.example.json")
DD = load_json(S / "01-editing-director/examples/director-decisions.example.json")
SCHEMA = load_json(HERE / "schemas/qa-report.schema.json")


def rules(rep):
    return {f["ruleId"] for f in rep["findings"]}


class TestReview(unittest.TestCase):
    def test_clean_examples_pass(self):
        r = R.Report()
        R.check_captions(r, TK, TR, 14.1)
        R.check_pacing(r, load_json(S / "04-smart-cut-pacing/examples/cut-list.example.json"), DD, TR, DD["effectBudget"])
        rep = R.finalize(r)
        self.assertEqual(validate(rep, SCHEMA), [])
        self.assertEqual(rep["gate"], "pass", rep["findings"])

    def test_invented_word_is_blocker(self):
        tk = copy.deepcopy(TK)
        tk["pages"][0]["words"][0]["text"] = "Siêu"
        r = R.Report()
        R.check_captions(r, tk, TR, 14.1)
        rep = R.finalize(r)
        self.assertIn("QA-CAP-06", rules(rep))
        self.assertEqual(rep["gate"], "fail")
        f = next(f for f in rep["findings"] if f["ruleId"] == "QA-CAP-06")
        self.assertEqual(f["suggestedFix"]["skill"], "smart-captions")

    def test_safe_area_and_face(self):
        tk = copy.deepcopy(TK)
        tk["pages"][2]["placement"]["y"] = 0.97
        r = R.Report()
        R.check_captions(r, tk, TR, 14.1, [{"startSec": 0, "endSec": 20, "box": {"x": 0.2, "y": 0.6, "w": 0.6, "h": 0.3}}])
        self.assertTrue({"QA-CAP-04", "QA-CAP-05"} <= rules(R.finalize(r)))

    def test_missing_inputs_reported_not_passed(self):
        r = R.Report()
        R.check_pacing(r, None, None, None, {})
        R.check_render(r, None, {"width": 1080, "height": 1920, "fps": 30}, {})
        rep = R.finalize(r)
        self.assertTrue(rep["notChecked"])

    def test_overwrite_blocker(self):
        r = R.Report()
        R.check_render(r, None, {"width": 1, "height": 1, "fps": 30}, {}, "a/in.mp4", "a/in.mp4")
        self.assertIn("QA-REN-06", rules(R.finalize(r)))

    def test_transition_in_hook(self):
        tp = {"transitions": [{"boundaryIndex": 1, "atSec": 0.8, "type": "zoom", "durationSec": 0.3}]}
        r = R.Report()
        R.check_transitions(r, tp, 2.0, 2)
        self.assertIn("QA-TR-01", rules(R.finalize(r)))

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_render_checks_detect_black_and_fps(self):
        d = U.tmpdir()
        v = d / "v.mp4"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=540x960:rate=25:duration=3",
               "-f", "lavfi", "-i", "sine=d=3", "-vf", "drawbox=c=black:t=fill:enable='between(t,1,1.6)'",
               "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(v)])
        import json
        import subprocess
        probe = json.loads(subprocess.run(R.detect_cmds(str(v))["probe"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)
        logs = {k: subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace").stderr for k, c in R.detect_cmds(str(v)).items() if k != "probe"}
        r = R.Report()
        R.check_render(r, probe, {"width": 1080, "height": 1920, "fps": 30}, logs)
        got = rules(R.finalize(r))
        self.assertIn("QA-REN-01", got)
        self.assertIn("QA-REN-03", got)
        U.run(R.contact_sheet_cmd(str(v), str(d / "sheet.png")))
        self.assertTrue((d / "sheet.png").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
