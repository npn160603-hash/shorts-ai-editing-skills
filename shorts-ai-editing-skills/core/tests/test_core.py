import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import sae_schema as S  # noqa: E402
import sae_text as X  # noqa: E402
import sae_timeline as T  # noqa: E402


class TestSchemaValidator(unittest.TestCase):
    def test_examples_valid(self):
        for inst, sch in [("core/examples/transcript.example.json", "core/schemas/transcript.schema.json"),
                          ("core/examples/capability-manifest.example.json", "core/schemas/capability-manifest.schema.json"),
                          ("core/examples/capability-manifest.demo-ffmpeg.json", "core/schemas/capability-manifest.schema.json"),
                          ("skills.registry.json", "core/schemas/skill-registry.schema.json")]:
            self.assertEqual(S.validate_file(ROOT / inst, ROOT / sch), [], inst)

    def test_rejects_bad(self):
        sch = S.load_json(ROOT / "core/schemas/transcript.schema.json")
        bad = {"language": "vi", "timebase": "elsewhere", "wordTimestampsReliable": True, "segments": [], "extra": 1}
        errs = S.validate(bad, sch)
        self.assertTrue(any("timebase" in e for e in errs))
        self.assertTrue(any("unexpected property 'extra'" in e for e in errs))

    def test_matches_jsonschema_if_installed(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed (optional cross-check)")
        for p in (ROOT).rglob("*.schema.json"):
            jsonschema.Draft202012Validator.check_schema(S.load_json(p))


class TestTimeline(unittest.TestCase):
    def test_keep_map_and_remap(self):
        segs = T.build_keep_map([(0.0, 2.0), (3.0, 5.0)])
        self.assertAlmostEqual(T.src_to_out(3.5, segs), 2.5)
        self.assertIsNone(T.src_to_out(2.5, segs))
        words = [{"text": "a", "startSec": 1.0, "endSec": 1.5}, {"text": "cut", "startSec": 2.2, "endSec": 2.8},
                 {"text": "b", "startSec": 3.1, "endSec": 3.4}]
        out = T.remap_words(words, segs)
        self.assertEqual([w["text"] for w in out], ["a", "b"])
        self.assertAlmostEqual(out[1]["startSec"], 2.1)

    def test_invert_merge(self):
        self.assertEqual(T.merge_ranges([(0, 1), (0.9, 2), (3, 4)]), [(0, 2), (3, 4)])
        self.assertEqual(T.invert_ranges([(1, 2)], 3), [(0.0, 1), (2, 3)])

    def test_reorder_rejected_without_offsets(self):
        with self.assertRaises(ValueError):
            T.build_keep_map([(3.0, 4.0), (1.0, 2.0)])


class TestText(unittest.TestCase):
    def test_vietnamese_graphemes_nfd(self):
        nfd = "Tiếng Việt".encode("utf-8").decode("utf-8")
        import unicodedata
        g = X.graphemes(unicodedata.normalize("NFD", nfd))
        self.assertEqual("".join(g), "Tiếng Việt")
        self.assertEqual(len(g), 10)
        self.assertIn("ế", g)

    def test_emoji_zwj(self):
        self.assertEqual(len(X.graphemes("👨‍👩‍👧 ok")), 4)

    def test_punct(self):
        self.assertTrue(X.ends_sentence("ngày?"))
        self.assertTrue(X.ends_clause("một:"))
        self.assertEqual(X.strip_punct("“phút,”"), "phút")


if __name__ == "__main__":
    unittest.main(verbosity=2)
