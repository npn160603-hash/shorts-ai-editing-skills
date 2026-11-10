import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib")]
import camera as C  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

DD = load_json(ROOT / "skills/01-editing-director/examples/director-decisions.example.json")
SRC = {"width": 1080, "height": 1920}
OUT = {"width": 1080, "height": 1920, "fps": 30}


class TestCamera(unittest.TestCase):
    def setUp(self):
        self.tk = C.build_track(DD, SRC, OUT, "center-weighted", cut_points=[2.0333, 8.0667])

    def test_schema(self):
        self.assertEqual(validate(self.tk, load_json(HERE / "schemas/camera-track.schema.json")), [])

    def test_never_outside_frame(self):
        for n in range(0, 14 * 30, 3):
            z, cx, cy = C.state_at(self.tk, n / 30)
            self.assertGreaterEqual(z, 1.0)
            self.assertGreaterEqual(cx - 0.5 / z, -1e-9)
            self.assertLessEqual(cx + 0.5 / z, 1 + 1e-9)

    def test_punch_has_release(self):
        types = [m["type"] for m in self.tk["moves"]]
        self.assertEqual(types.count("punch-in"), types.count("punch-out"))

    def test_low_res_source_disables_zoom(self):
        tk = C.build_track(DD, {"width": 1920, "height": 1080}, OUT)
        self.assertEqual(tk["maxZoom"], 1.0)
        self.assertTrue(all(m.get("toZoom", 1) <= 1.0 for m in tk["moves"]))
        self.assertTrue(tk["warnings"])

    def test_subject_focus(self):
        boxes = [{"startSec": 0, "endSec": 20, "box": {"x": 0.55, "y": 0.2, "w": 0.3, "h": 0.2}}]
        tk = C.build_track(DD, SRC, OUT, "subject-focus", subject_boxes=boxes)
        z, cx, cy = C.state_at(tk, 5.1)
        self.assertGreater(cx, 0.5)

    def test_shake_deterministic(self):
        dd = dict(DD, intensity="dynamic")
        a = C.build_track(dd, SRC, OUT, allow_shake=True, seed=3)
        b = C.build_track(dd, SRC, OUT, allow_shake=True, seed=3)
        self.assertEqual([C.state_at(a, t / 30) for t in range(150, 160)], [C.state_at(b, t / 30) for t in range(150, 160)])

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_ffmpeg_zoom_render(self):
        d = U.tmpdir()
        src = U.make_source(d / "src.mp4", 4.0)
        tk = {"cameraTrackVersion": "1.0", "timebase": "output", "mode": "t", "source": SRC, "output": OUT, "maxZoom": 1.3, "seed": 1,
              "moves": [{"id": "m01", "type": "punch-in", "startSec": 2.0, "durationSec": 0, "fromZoom": 1, "toZoom": 1.2,
                         "fromCenter": [0.5, 0.5], "toCenter": [0.5, 0.5], "easing": "step"}]}
        out = d / "cam.mp4"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vf", C.ffmpeg_filter(tk), "-an",
               "-c:v", "libx264", "-preset", "ultrafast", str(out)])
        v = next(s for s in U.probe(out)["streams"] if s["codec_type"] == "video")
        self.assertEqual((v["width"], v["height"]), (1080, 1920))
        before = U.mean_abs_diff(U.frame_rgb(src, 1.0), U.frame_rgb(out, 1.0))
        after = U.mean_abs_diff(U.frame_rgb(src, 3.0), U.frame_rgb(out, 3.0))
        self.assertLess(before, 3.0)      # no zoom yet: same picture
        self.assertGreater(after, before + 5.0)  # zoomed: picture differs


if __name__ == "__main__":
    unittest.main(verbosity=2)
