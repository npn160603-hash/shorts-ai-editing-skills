import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib")]
import captions as C  # noqa: E402
import sae_fontmetrics  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

TR = load_json(ROOT / "skills/04-smart-cut-pacing/examples/transcript.output-time.example.json")
DD = load_json(ROOT / "skills/01-editing-director/examples/director-decisions.example.json")
VIDEO = {"width": 1080, "height": 1920}
SAFE = {"left": 0.06, "right": 0.06, "top": 0.1, "bottom": 0.19}
FACE = [{"startSec": 5.0, "endSec": 8.0, "box": {"x": 0.3, "y": 0.55, "w": 0.4, "h": 0.25}}]
V11 = ROOT.parent / "shorts-motion-designer/schemas/shorts-motion-plan.schema.json"


def page_lines(p):
    return [" ".join(p["words"][i]["text"] for i in ln) for ln in p["lines"]]


class TestCaptions(unittest.TestCase):
    def setUp(self):
        self.tk = C.build_track(TR, VIDEO, SAFE, "clean-bold", DD, FACE)

    def test_schema(self):
        self.assertEqual(validate(self.tk, load_json(HERE / "schemas/caption-track.schema.json")), [])
        self.assertEqual(validate(load_json(HERE / "examples/caption-style-presets.json"),
                                  load_json(HERE / "schemas/caption-style-presets.schema.json")), [])

    def test_all_words_kept_in_order(self):
        got = [w["text"] for p in self.tk["pages"] for w in p["words"]]
        self.assertEqual(got, [w["text"] for w in TR["words"]])

    def test_no_compound_or_number_unit_split(self):
        for p in C.build_track(TR, VIDEO, SAFE, "punchy-3", DD)["pages"] + self.tk["pages"]:
            texts = [w["text"] for w in p["words"]]
            self.assertNotEqual(texts[-1:], ["lãng"])
            self.assertNotEqual(texts[-1:], ["25"])
        for p in self.tk["pages"]:
            for ln in page_lines(p):
                self.assertFalse(ln.endswith(" lãng") or ln.endswith(" 25"), ln)

    def test_max_lines_and_pages_ordered(self):
        prev = 0.0
        for p in self.tk["pages"]:
            self.assertLessEqual(len(p["lines"]), 2)
            self.assertGreaterEqual(p["startSec"], prev - 1e-6)
            prev = p["endSec"]

    def test_avoids_face(self):
        moved = [p for p in self.tk["pages"] if 5.0 <= p["startSec"] < 8.0]
        self.assertTrue(moved)
        for p in moved:
            self.assertLess(p["placement"]["y"], 0.5)

    def test_headline_for_hook(self):
        self.assertEqual(self.tk["pages"][0]["captionMode"], "headline")
        self.assertEqual(self.tk["pages"][0]["animationIn"], "hook-reveal")

    def test_phrase_mode_never_fakes_words(self):
        tk = C.build_track(dict(TR, wordTimestampsReliable=False), VIDEO, SAFE, "clean-bold", DD)
        self.assertEqual(tk["mode"], "phrase")
        self.assertTrue(all(p["timing"] == "estimated-phrase" for p in tk["pages"]))
        self.assertNotIn("\\fscx108", C.to_ass(tk))

    def test_ass_word_events(self):
        ass = C.to_ass(self.tk)
        self.assertIn("PlayResY: 1920", ass)
        n_words = sum(len(p["words"]) for p in self.tk["pages"])
        self.assertEqual(ass.count("Dialogue:"), n_words)
        self.assertIn("lãng", ass)

    def test_motion_plan_compatible_with_v11(self):
        kws = [a for a in DD["accents"] if a["type"] == "keyword-pop"]
        mp = C.to_motion_plan(self.tk, 30, 14.1, keyword_callouts=kws)
        if not V11.is_file():
            self.skipTest("shorts-motion-designer V1.1 not found next to this package")
        self.assertEqual(validate(mp, load_json(V11)), [])

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_burn_ass(self):
        d = U.tmpdir()
        src = U.make_source(d / "src.mp4", 4.0)
        ass = d / "c.ass"
        ass.write_text(C.to_ass(self.tk), encoding="utf-8")
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vf", C.ffmpeg_subtitles_filter(str(ass), str(sae_fontmetrics.FONTS_DIR)),
               "-c:a", "copy", "-c:v", "libx264", "-preset", "ultrafast", str(d / "o.mp4")])
        self.assertGreater(U.mean_abs_diff(U.frame_rgb(src, 0.5), U.frame_rgb(d / "o.mp4", 0.5)), 0.3)  # text drawn

    def test_real_font_metrics_used(self):
        self.assertEqual(self.tk["fontCheck"]["metrics"], "font-file")
        self.assertEqual(self.tk["fontCheck"]["missingGlyphs"], [])

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_rendered_lines_stay_inside_safe_area(self):
        """Burn a long Vietnamese sentence on black with the bundled font and measure ink."""
        text = "Những thói quen buổi sáng đơn giản giúp bạn tập trung hiệu quả hơn mỗi ngày làm việc"
        ws, t = [], 0.0
        for w in text.split():
            ws.append({"text": w, "startSec": round(t, 3), "endSec": round(t + 0.25, 3)})
            t += 0.3
        tr = {"language": "vi", "timebase": "output", "wordTimestampsReliable": True,
              "segments": [{"id": "s1", "text": text, "startSec": 0, "endSec": t}], "words": ws}
        safe = dict(SAFE)
        tk = C.build_track(tr, VIDEO, safe, "clean-bold")
        d = U.tmpdir()
        ass = d / "c.ass"
        ass.write_text(C.to_ass(tk), encoding="utf-8")
        W, H = 1080, 1920
        for p in tk["pages"]:
            mid = (p["startSec"] + p["endSec"]) / 2
            raw = U.run_bytes(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:d={t + 1}",
                               "-vf", C.ffmpeg_subtitles_filter(str(ass), str(sae_fontmetrics.FONTS_DIR)), "-ss", f"{mid}",
                               "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"])
            xs = [x for y in range(0, H, 4) for x in range(0, W, 2) if raw[y * W + x] > 60]
            self.assertTrue(xs, p["id"])
            self.assertGreaterEqual(min(xs), safe["left"] * W - 2, p["id"])
            self.assertLessEqual(max(xs), (1 - safe["right"]) * W + 2, p["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
