import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "core" / "lib")]
import sae_testutil as U  # noqa: E402
import subject_boxes as S  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

SCHEMA = load_json(ROOT / "core/schemas/subject-boxes.schema.json")


def _cascade_ok():
    try:
        S.haar_path()
        return True
    except Exception:
        return False


class TestTracking(unittest.TestCase):
    def test_track_merges_and_splits(self):
        dets = [{"t": 0.0, "box": (0.3, 0.3, 0.2, 0.15)}, {"t": 0.25, "box": (0.31, 0.3, 0.2, 0.15)},
                {"t": 0.5, "box": (0.3, 0.31, 0.2, 0.15)}, {"t": 2.0, "box": (0.6, 0.6, 0.2, 0.15)}]
        out = S.track(dets, 0.25)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["startSec"], 0.0)
        self.assertAlmostEqual(out[0]["endSec"], 0.75)
        sb = {"subjectBoxesVersion": "1.0", "timebase": "source", "detector": "t", "boxes": out}
        self.assertEqual(validate(sb, SCHEMA), [])

    def test_remap_to_output(self):
        sb = {"subjectBoxesVersion": "1.0", "timebase": "source", "detector": "t",
              "boxes": [{"startSec": 1.0, "endSec": 5.0, "box": {"x": 0.3, "y": 0.3, "w": 0.2, "h": 0.2}}]}
        cl = {"segments": [{"srcStartSec": 0.0, "srcEndSec": 2.0}, {"srcStartSec": 3.0, "srcEndSec": 6.0}]}
        out = S.remap_to_output(sb, cl)
        self.assertEqual([(b["startSec"], b["endSec"]) for b in out["boxes"]], [(1.0, 2.0), (2.0, 4.0)])


@unittest.skipUnless(S.available() and _cascade_ok() and U.HAVE_FFMPEG, "OpenCV 4.x with bundled cascade + ffmpeg required")
class TestDetect(unittest.TestCase):
    def test_detects_face_in_real_photo(self):
        try:
            from skimage import data
        except ImportError:
            self.skipTest("scikit-image not installed (only used for a public-domain test face)")
        import cv2
        d = U.tmpdir()
        cv2.imwrite(str(d / "a.png"), cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR))
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(d / "a.png"), "-t", "2",
               "-vf", "scale=1080:-2,pad=1080:1920:0:500,format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", str(d / "f.mp4")])
        r = S.detect(str(d / "f.mp4"))
        self.assertEqual(validate(r, SCHEMA), [])
        self.assertTrue(r["boxes"])
        b = r["boxes"][0]["box"]
        self.assertTrue(0.25 < b["y"] < 0.5 and 0.2 < b["x"] < 0.5, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
