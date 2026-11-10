import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib")]
import sae_testutil as U  # noqa: E402
import vfx as V  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

DD = load_json(ROOT / "skills/01-editing-director/examples/director-decisions.example.json")
ALL = {"vfx.colorAdjust": "implemented", "vfx.glow": "implemented", "vfx.blur": "implemented"}


class TestVfx(unittest.TestCase):
    def test_schema(self):
        p = V.plan_vfx(DD, ALL, "normal", duration=14.1)
        self.assertEqual(validate(p, load_json(HERE / "schemas/vfx-plan.schema.json")), [])

    def test_only_climax_and_limit(self):
        p = V.plan_vfx(DD, ALL, "subtle", duration=14.1)
        self.assertLessEqual(len([i for i in p["items"] if i["scope"] == "window"]), 1)

    def test_no_caps_no_effects(self):
        p = V.plan_vfx(DD, {}, "dynamic", duration=14.1)
        self.assertEqual(p["items"], [])
        self.assertEqual(V.ffmpeg_chain(p), "null")

    def test_params_clamped(self):
        self.assertEqual(V._p("soft-glow", {"opacity": 5})["opacity"], 0.4)

    def test_budget_drops_window_effects(self):
        p = V.plan_vfx(DD, ALL, "dynamic", duration=1.0, hardware_budget=0.5)
        self.assertTrue(all(i["scope"] == "global" for i in p["items"]))

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_render(self):
        d = U.tmpdir()
        src = U.make_source(d / "src.mp4", 3.0)
        p = {"vfxPlanVersion": "1.0", "timebase": "output", "layer": "base-video-before-captions", "items": [
            {"id": "fx01", "effect": "soft-glow", "scope": "window", "startSec": 1.0, "durationSec": 0.5, "params": {"sigma": 18, "opacity": 0.3}, "reason": "t"},
            {"id": "fx02", "effect": "vignette", "scope": "global", "startSec": 0, "durationSec": 3, "params": {"angle": 0.45}, "reason": "t"}]}
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vf", V.ffmpeg_chain(p), "-an",
               "-c:v", "libx264", "-preset", "ultrafast", str(d / "o.mp4")])
        self.assertTrue((d / "o.mp4").stat().st_size > 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
