import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib")]
import pacing as P  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

TR = load_json(ROOT / "core/examples/transcript.example.json")
LOG = (HERE / "examples/silencedetect.log.txt").read_text()
SCHEMA = load_json(HERE / "schemas/cut-list.schema.json")


class TestPacing(unittest.TestCase):
    def test_parse_silencedetect_open_tail(self):
        s = P.parse_silencedetect(LOG, 17.0)
        self.assertEqual(s[0], (0.0, 0.38))
        self.assertEqual(s[-1], (16.33, 17.0))

    def test_cut_list_valid_and_bounded(self):
        cl = P.plan_cuts(TR, 17.0, 30, "normal", 0.35, silence_log=LOG)
        self.assertEqual(validate(cl, SCHEMA), [])
        self.assertLessEqual(cl["stats"]["removedRatio"], 0.35)
        reasons = {r["reason"] for r in cl["removed"]}
        self.assertTrue({"head", "tail", "silence", "filler"} <= reasons)
        for s in cl["segments"]:  # frame-snapped
            self.assertAlmostEqual(s["srcStartSec"] * 30, round(s["srcStartSec"] * 30), places=2)

    def test_no_word_inside_removed_region(self):
        cl = P.plan_cuts(TR, 17.0, 30, "normal", 0.35, silence_log=LOG)
        out = P.remap_transcript(TR, cl)
        self.assertNotIn("Ừm,", [w["text"] for w in out["words"]])
        self.assertEqual(len(out["words"]), len(TR["words"]) - 1)
        self.assertFalse(out["segments"][1]["text"].startswith("Ừm"))

    def test_budget_rejects(self):
        cl = P.plan_cuts(TR, 17.0, 30, "dynamic", 0.05, silence_log=LOG)
        self.assertLessEqual(cl["stats"]["removedRatio"], 0.05 + 1e-6)
        self.assertTrue(cl["rejected"])

    def test_word_gap_mode_without_log(self):
        cl = P.plan_cuts(TR, 17.0, 30, "normal", 0.35)
        self.assertTrue(all(r["method"] == "heuristic" for r in cl["removed"]))

    def test_ai_removals_must_be_labelled(self):
        with self.assertRaises(ValueError):
            P.plan_cuts(TR, 17.0, 30, semantic_removals=[{"srcStartSec": 1, "srcEndSec": 2, "reason": "semantic", "method": "heuristic", "confidence": 0.5}])

    def test_retake(self):
        segs = [{"id": "a", "text": "Mẹo số một là tắt", "startSec": 0, "endSec": 1},
                {"id": "b", "text": "Mẹo số một là tắt thông báo", "startSec": 1.2, "endSec": 3}]
        self.assertEqual(P.find_retakes(segs)[0]["srcEndSec"], 1.2)

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_ffmpeg_render_frame_exact(self):
        d = U.tmpdir()
        src = U.make_source(d / "src.mp4", 17.0)
        cl = P.plan_cuts(TR, 17.0, 30, "normal", 0.35, silence_log=LOG)
        out = d / "cut.mp4"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src), "-filter_complex", P.ffmpeg_concat_filter(cl),
               "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(out)])
        pr = U.probe(out)
        v = next(s for s in pr["streams"] if s["codec_type"] == "video")
        a = next(s for s in pr["streams"] if s["codec_type"] == "audio")
        self.assertEqual(int(v["nb_read_frames"]), round(cl["stats"]["outputDurationSec"] * 30))
        self.assertLess(abs(float(a["duration"]) - float(v["duration"])), 1 / 30 + 0.025)


if __name__ == "__main__":
    unittest.main(verbosity=2)
