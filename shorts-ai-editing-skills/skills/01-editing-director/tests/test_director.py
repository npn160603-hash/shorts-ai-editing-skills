import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib")]
import director as D  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

TR = load_json(ROOT / "skills/04-smart-cut-pacing/examples/transcript.output-time.example.json")
CL = load_json(ROOT / "skills/04-smart-cut-pacing/examples/cut-list.example.json")
CUTS = [s["outStartSec"] for s in CL["segments"][1:]]
DUR = CL["stats"]["outputDurationSec"]


class TestDirector(unittest.TestCase):
    def setUp(self):
        self.an = D.analyze(TR, DUR)
        self.dd = D.decide(self.an, "normal", None, CUTS, TR["words"])

    def test_schemas(self):
        self.assertEqual(validate(self.an, load_json(HERE / "schemas/content-analysis.schema.json")), [])
        self.assertEqual(validate(self.dd, load_json(HERE / "schemas/director-decisions.schema.json")), [])

    def test_roles(self):
        roles = [s["role"] for s in self.an["segments"]]
        self.assertEqual(roles[0], "hook")
        self.assertEqual(roles[-1], "cta")
        self.assertIn("climax", roles)

    def test_keywords_are_real_text(self):
        full = " ".join(s["text"] for s in TR["segments"]).lower()
        for a in self.dd["accents"]:
            if a.get("target"):
                self.assertIn(a["target"].lower().split()[0], full)

    def test_cta_and_restraint(self):
        cta = next(s for s in self.dd["segments"] if s["role"] == "cta")
        self.assertTrue(cta["restraint"])
        self.assertFalse([a for a in self.dd["accents"] if a.get("segmentId") == cta["segmentId"]])

    def test_budget_rolling_window(self):
        b = self.dd["effectBudget"]
        ov = [a for a in self.dd["accents"] if a["type"] in ("keyword-pop", "callout", "headline")]
        for a in ov:
            self.assertLessEqual(sum(1 for x in ov if abs(x["atSec"] - a["atSec"]) < 5), b["maxAccentsPer10s"])

    def test_no_overlapping_camera(self):
        cam = [a for a in self.dd["accents"] if a["type"] in ("punch-in", "smooth-push", "jump-cut-reframe")]
        for x, y in zip(cam, cam[1:]):
            self.assertGreaterEqual(y["atSec"], x["atSec"] + x["durationSec"] - 1e-6)

    def test_sincere_gets_no_accents(self):
        tr = dict(TR, segments=[dict(TR["segments"][0]), {"id": "z", "text": "Thật lòng cảm ơn các bạn rất nhiều 100 lần",
                                                          "startSec": 3.0, "endSec": 6.0}])
        dd = D.decide(D.analyze(tr, 6.0), "dynamic")
        self.assertFalse([a for a in dd["accents"] if a.get("segmentId") == "z"])

    def test_subtle_has_fewer_accents(self):
        sub = D.decide(self.an, "subtle", None, CUTS, TR["words"])
        dyn = D.decide(self.an, "dynamic", None, CUTS, TR["words"])
        self.assertLessEqual(len(sub["accents"]), len(dyn["accents"]))

    def test_ai_override_keywords_respected(self):
        an = D.analyze(TR, DUR, ai_overrides={"s3": {"role": "climax", "importance": 7, "keywords": ["thông báo", "bịa ra"]}})
        s3 = next(s for s in an["segments"] if s["id"] == "s3")
        self.assertEqual(s3["roleSource"], "ai")
        self.assertEqual(s3["keywords"], ["thông báo"])   # invented keyword dropped
        self.assertEqual(s3["importance"], 1.0)           # clamped

    def test_requires_output_time(self):
        with self.assertRaises(ValueError):
            D.analyze(dict(TR, timebase="source"), DUR)


if __name__ == "__main__":
    unittest.main(verbosity=2)
