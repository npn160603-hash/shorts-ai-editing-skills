"""v1.3 modules: overlays, highlights, story, publish, TTS (test backend), LLM (mocked), safe-zone tool.
FFmpeg-dependent tests skip when ffmpeg is absent."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator" / "lib"), str(ROOT / "core" / "lib"), str(ROOT / "tools")]
import runner  # noqa: E402,F401  (sets up skill lib paths)
import overlays as OV  # noqa: E402
import highlights as HL  # noqa: E402
import publish as PB  # noqa: E402
import story as ST  # noqa: E402
import sae_tts  # noqa: E402
import sae_llm  # noqa: E402
from sae_schema import load_json  # noqa: E402

S = ROOT / "skills"
TRACK = load_json(S / "02-smart-captions/examples/caption-track.example.json")
DD = load_json(S / "01-editing-director/examples/director-decisions.example.json")
TR = load_json(ROOT / "core/examples/transcript.example.json")
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def long_transcript(n=30, step=4.0):
    texts = ["Bạn có biết vì sao mọi người luôn thiếu thời gian?", "Đây là cách đơn giản nhất để lấy lại hai giờ mỗi ngày.",
             "Thứ nhất, hãy tắt thông báo điện thoại.", "Kết quả là năng suất tăng gấp đôi.",
             "Ừm thì, à, nói chung là vậy.", "Đăng ký kênh để xem thêm nhé."]
    segs, words, t = [], [], 0.0
    for i in range(n):
        tx = texts[i % len(texts)]
        ws = tx.split()
        d = step - 0.5
        segs.append({"id": f"s{i + 1}", "text": tx, "startSec": round(t, 3), "endSec": round(t + d, 3)})
        for k, w in enumerate(ws):
            a = t + d * k / len(ws)
            words.append({"text": w, "startSec": round(a, 3), "endSec": round(a + d / len(ws) * 0.9, 3)})
        t += step
    return {"language": "vi", "timebase": "source", "wordTimestampsReliable": True, "segments": segs, "words": words}


class TestOverlays(unittest.TestCase):
    def test_events_and_merge(self):
        styles, ev, used = OV.overlay_events(TRACK, DD, 12.0, {"cta": "Theo dõi để xem phần 2"})
        self.assertEqual(len(styles), 4)
        self.assertTrue(used["progressBar"])
        self.assertEqual(used["cta"], "Theo dõi để xem phần 2")
        cta = [e for e in ev if ",OvCta," in e][0]
        self.assertIn("\\move(", cta)
        self.assertNotIn("\\pos(", cta)
        bar = [e for e in ev if ",OvBar," in e][0]
        self.assertIn("\\clip(", bar)
        ass = "[V4+ Styles]\nFormat: Name\nStyle: Cap,x\n\n[Events]\nFormat: Layer, Start\nDialogue: 1,a\n"
        out = OV.merge_into_ass(ass, styles, ev)
        self.assertLess(out.index("Style: OvHook"), out.index("[Events]"))
        self.assertLess(out.index("OvBar,,"), out.index("Dialogue: 1,a"))

    def test_toggles_off_and_no_invented_text(self):
        _, ev, used = OV.overlay_events(TRACK, DD, 12.0, {"hookTitle": None, "keywordCallouts": False,
                                                          "progressBar": False, "cta": None})
        self.assertEqual(ev, [])
        self.assertIsNone(used["hookTitle"])
        self.assertIsNone(OV._hook_title(None, "auto"))
        self.assertEqual(OV._hook_title(DD, "MY TITLE"), "MY TITLE")


class TestHighlights(unittest.TestCase):
    def test_find_non_overlapping(self):
        t = long_transcript()
        h = HL.find_highlights(t, count=3, min_sec=15, max_sec=30)
        self.assertGreaterEqual(h["count"], 2)
        cl = h["clips"]
        for a, b in zip(cl, cl[1:]):
            self.assertLessEqual(a["endSec"] + 2.0, b["startSec"] + 1e-6)
        for c in cl:
            self.assertTrue(15 <= c["durationSec"] <= 30)
            self.assertTrue(c["id"].startswith("clip-"))

    def test_bonus_bounded(self):
        t = long_transcript(12)
        base = HL.find_highlights(t, count=1, min_sec=15, max_sec=30)
        boosted = HL.find_highlights(t, count=1, min_sec=15, max_sec=30, bonus=lambda c: 99)
        self.assertAlmostEqual(boosted["clips"][0]["score"] - 1.0, base["clips"][0]["score"], places=3)

    def test_slice_offset(self):
        t = long_transcript(6)
        s = HL.slice_transcript(t, 4.0, 12.0, offset=3.85)
        self.assertEqual([x["id"] for x in s["segments"]], ["s2", "s3"])
        self.assertAlmostEqual(s["segments"][0]["startSec"], 0.15, places=3)
        self.assertTrue(all(w["startSec"] >= 0 for w in s["words"]))

    def test_extract_cmd_never_overwrites(self):
        cmd = HL.extract_cmd("in.mp4", 10, 20, "out.mp4")
        self.assertIn("-n", cmd)
        self.assertNotIn("-y", cmd)


class TestPublish(unittest.TestCase):
    def test_suggest(self):
        k = PB.suggest(TR, None, ["tiktok", "youtube-shorts"], credits=[{"source": "pexels", "author": "A"}])
        self.assertTrue(k["titles"])
        self.assertTrue(all(len(x) <= 71 for x in k["titles"]))
        self.assertIn("#shorts", k["hashtags"])
        self.assertTrue(all(h.startswith("#") and not h[1].isdigit() for h in k["hashtags"]))
        self.assertIn("Footage: pexels / A", k["description"])

    def test_helpers(self):
        self.assertEqual(PB._tag("Đồng hồ"), "#dongho")
        self.assertEqual(PB._tag("2 giờ"), "")
        self.assertTrue(PB._cut("a " * 60, 20).endswith("…"))
        self.assertEqual(PB._cap("xin chào"), "Xin chào")


class TestLLMMocked(unittest.TestCase):
    def http(self, payload):
        return lambda url, body: json.dumps({"response": json.dumps(payload)})

    def test_parsers(self):
        self.assertEqual(sae_llm.title_ideas("m", "x", http=self.http({"titles": ["A", " ", "B"]})), ["A", "B"])
        self.assertEqual(sae_llm.rate_highlights("m", [{"firstSentence": "a", "durationSec": 20, "keywords": []}],
                                                 http=self.http({"0": 3, "x": 1})), {0: 1.0})
        ov = sae_llm.segment_overrides("m", [{"id": "s1", "text": "a"}], http=self.http({"s1": {"role": "hook"}, "s2": 5}))
        self.assertEqual(ov, {"s1": {"role": "hook"}})


class TestStoryParse(unittest.TestCase):
    def test_parse_script(self):
        p = ST.parse_script("# comment\n[scene: coffee morning] Câu một. Câu hai!\nCâu ba [clip: x.mp4]\n")
        self.assertEqual([x["text"] for x in p], ["Câu một.", "Câu hai!", "Câu ba"])
        self.assertEqual(p[0]["scene"], "coffee morning")
        self.assertIsNone(p[1]["scene"])
        self.assertEqual(p[2]["clip"], "x.mp4")

    def test_library_and_pick(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "coffee").mkdir()
            (Path(d) / "coffee" / "cup.jpg").write_bytes(b"x")
            (Path(d) / "city.png").write_bytes(b"x")
            lib = ST.load_library([d])
            self.assertEqual(len(lib), 2)
            self.assertTrue(all(x["license"].startswith("own") for x in lib))
            best = ST.pick_scene({"text": "x", "scene": "coffee"}, lib, {})
            self.assertTrue(best["file"].endswith("cup.jpg"))
            self.assertIsNone(ST.pick_scene({"text": "x"}, [], {}))
            with self.assertRaises(FileNotFoundError):
                ST.pick_scene({"text": "x", "clip": str(Path(d) / "missing.mp4")}, lib, {})


@unittest.skipUnless(HAS_FF, "ffmpeg not installed")
class TestFfmpegV13(unittest.TestCase):
    def test_tts_and_story_assemble(self):
        with tempfile.TemporaryDirectory() as d:
            v = sae_tts.synth_sentences(["Câu thứ nhất.", "Câu thứ hai dài hơn một chút."], d, "test", gap=0.2)
            self.assertTrue(Path(v["voice"]).is_file())
            self.assertAlmostEqual(sae_tts.duration(v["voice"]), v["durationSec"], delta=0.15)
            self.assertLess(v["sentences"][0]["endSec"], v["sentences"][1]["startSec"])
            img = Path(d) / "a.png"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x240", "-frames:v", "1", str(img)], check=True)
            scene = {"file": str(img), "kind": "image", "source": "local", "author": "", "pageUrl": "", "license": "own"}
            r = ST.assemble([{"text": "a"}, {"text": "b"}], v, [scene, None], Path(d) / "out", width=270, height=480, fps=15)
            self.assertEqual(r["missingScenes"], 1)
            self.assertTrue(Path(r["base"]).is_file())
            self.assertEqual(len(json.loads(Path(r["credits"]).read_text(encoding="utf-8"))), 1)
            tr = ST.transcript_from_voice(v, "vi")
            self.assertFalse(tr["wordTimestampsReliable"])
            self.assertEqual(len(tr["segments"]), 2)

    def test_safe_zone_tool(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "s.png", Path(d) / "o.png"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=540x960", "-frames:v", "1", str(src)], check=True)
            r = subprocess.run([sys.executable, str(ROOT / "tools/safe_zone_check.py"), str(src), "--out", str(out)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
