import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import sae_asr as A  # noqa: E402
import sae_media as M  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

EX = ROOT / "core/examples/asr"
SCHEMA = load_json(ROOT / "core/schemas/transcript.schema.json")


class TestAsr(unittest.TestCase):
    def test_faster_whisper(self):
        t = A.load_any(EX / "faster-whisper.example.json")
        self.assertEqual(validate(A.strict(t), SCHEMA), [])
        self.assertTrue(t["wordTimestampsReliable"], t["reliabilityNotes"])
        self.assertEqual(t["words"][0]["text"], "Bạn")          # leading space stripped
        self.assertEqual(t["segments"][1]["id"], "s2")

    def test_whisper_cpp_joins_subword_tokens(self):
        t = A.load_any(EX / "whisper-cpp.example.json")
        self.assertEqual(validate(A.strict(t), SCHEMA), [])
        self.assertEqual([w["text"] for w in t["words"]], ["Bạn", "đang", "lãng", "phí", "thời", "gian"])
        self.assertAlmostEqual(t["words"][2]["endSec"], 1.0)

    def test_srt_is_never_word_reliable(self):
        t = A.load_any(EX / "subtitles.example.srt")
        self.assertEqual(validate(A.strict(t), SCHEMA), [])
        self.assertFalse(t["wordTimestampsReliable"])
        self.assertEqual(t["segments"][1]["text"], "Đây là 3 mẹo.")
        self.assertNotIn("words", t)

    def test_native_format_roundtrip(self):
        t = A.load_any(ROOT / "core/examples/transcript.example.json")
        self.assertTrue(t["wordTimestampsReliable"])
        self.assertEqual(validate(A.strict(t), SCHEMA), [])

    def test_faster_whisper_objects(self):
        import sae_transcribe as TR
        from types import SimpleNamespace as N
        segs = [N(start=0.4, end=1.4, text=" Xin chào bạn", words=[N(word=" Xin", start=0.4, end=0.7, probability=0.9),
                                                                N(word=" chào", start=0.72, end=1.0, probability=0.9),
                                                                N(word=" bạn", start=1.02, end=1.38, probability=0.9)])]
        t = A.from_whisper(TR.segments_to_whisper_json(segs, "vi"), "vi")
        self.assertEqual([w["text"] for w in t["words"]], ["Xin", "chào", "bạn"])
        self.assertTrue(t["wordTimestampsReliable"])

    def test_sanity_rejects_backwards(self):
        segs = [{"id": "s1", "text": "a b c", "startSec": 0, "endSec": 3}]
        ws = [{"text": "a", "startSec": 1.0, "endSec": 1.2}, {"text": "b", "startSec": 0.2, "endSec": 0.4},
              {"text": "c", "startSec": 2.0, "endSec": 2.2}]
        ok, why = A.sanity_check_words(ws, segs)
        self.assertFalse(ok)
        self.assertTrue(any("backwards" in r for r in why))

    def test_nfd_input_normalised(self):
        import unicodedata
        data = {"segments": [{"start": 0, "end": 1, "text": unicodedata.normalize("NFD", "Tiếng Việt"),
                              "words": [{"word": unicodedata.normalize("NFD", " Tiếng"), "start": 0, "end": 0.4},
                                        {"word": unicodedata.normalize("NFD", " Việt"), "start": 0.45, "end": 0.9}]}]}
        t = A.from_whisper(data, "vi")
        self.assertEqual(t["words"][1]["text"], "Việt")
        self.assertEqual(t["segments"][0]["text"], "Tiếng Việt")


@unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
class TestMedia(unittest.TestCase):
    def test_cfr_and_vfr_detection_and_normalize(self):
        d = U.tmpdir()
        cfr = U.make_source(d / "cfr.mp4", 3.0)
        self.assertFalse(M.is_vfr(str(cfr))["vfr"])
        vfr = d / "vfr.mp4"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=3",
               "-vf", "select='if(lt(n\\,40)\\,1\\,not(mod(n\\,3)))'", "-fps_mode", "vfr",
               "-c:v", "libx264", "-preset", "ultrafast", str(vfr)])
        r = M.is_vfr(str(vfr))
        self.assertTrue(r["vfr"], r)
        out = d / "vfr_cfr.mp4"
        U.run(M.normalize_cmd(str(vfr), str(out), fps=30, copy_audio=False))
        self.assertFalse(M.is_vfr(str(out))["vfr"])
        with self.assertRaises(ValueError):
            M.normalize_cmd(str(out), str(out))

    def test_probe(self):
        d = U.tmpdir()
        p = M.probe_media(str(U.make_source(d / "s.mp4", 2.0)))
        self.assertEqual((p["width"], p["height"]), (1080, 1920))
        self.assertTrue(p["hasAudio"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
