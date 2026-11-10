import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "lib"))
sys.path.insert(0, str(ROOT / "orchestrator" / "lib"))
import orchestrate as O  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

REQ = load_json(ROOT / "orchestrator/examples/edit-request.example.json")
MAN = load_json(ROOT / "core/examples/capability-manifest.example.json")
DEMO = load_json(ROOT / "core/examples/capability-manifest.demo-ffmpeg.json")
REG = load_json(ROOT / "skills.registry.json")
SCHEMA = load_json(ROOT / "orchestrator/schemas/orchestration-plan.schema.json")


def by_id(plan):
    return {s["id"]: s for s in plan["skills"]}


class TestOrchestrator(unittest.TestCase):
    def test_intent_from_sample_instruction(self):
        i = O.parse_intent(REQ["instruction"])
        for k in ("cut", "captions", "camera", "audio", "speechPriority"):
            self.assertTrue(i[k], k)
        self.assertFalse(i["vfx"])
        self.assertEqual(i["intensity"], "normal")
        self.assertEqual(i["style"], "professional")

    def test_english_and_dynamic(self):
        i = O.parse_intent("Make it energetic, add captions and cut silence")
        self.assertTrue(i["captions"] and i["cut"])
        self.assertEqual(i["intensity"], "dynamic")

    def test_plan_valid_and_honest(self):
        p = O.plan(REQ, MAN, REG)
        self.assertEqual(validate(p, SCHEMA), [])
        s = by_id(p)
        self.assertEqual(s["camera-movement"]["status"], "blocked")          # documented only
        self.assertIn("camera.transform", s["camera-movement"]["needsIntegration"])
        self.assertEqual(s["cinematic-vfx"]["status"], "skipped")            # opt-in
        self.assertEqual(s["advanced-transitions"]["mode"], "hard-cut-only")
        ids = [st["id"] for st in p["stages"]]
        self.assertLess(ids.index("cut"), ids.index("direct"))
        self.assertLess(ids.index("captions"), ids.index("audio"))
        self.assertNotIn("camera", ids)

    def test_demo_manifest_full(self):
        p = O.plan(REQ, DEMO, REG)
        s = by_id(p)
        self.assertIn(s["camera-movement"]["status"], ("planned", "fallback"))   # no subject boxes -> center-weighted
        self.assertTrue(s["camera-movement"]["mode"].startswith("center-weighted"))
        self.assertEqual(s["smart-captions"]["mode"].split(";")[0], "word-highlight")
        self.assertTrue(s["audio-director"]["mode"].startswith("speech-first"))
        self.assertNotIn("duck", s["audio-director"]["mode"])                 # music not allowed in request

    def test_no_word_timestamps_falls_back(self):
        m = copy.deepcopy(DEMO)
        m["capabilities"]["transcript.wordTimestamps"] = {"status": "missing"}
        s = by_id(O.plan(REQ, m, REG))
        self.assertEqual(s["smart-captions"]["status"], "fallback")
        self.assertTrue(s["smart-captions"]["mode"].startswith("phrase"))

    def test_all_disabled_only_infrastructure(self):
        reg = copy.deepcopy(REG)
        for sk in reg["skills"]:
            if sk["id"] != "ai-editing-orchestrator":
                sk["enabled"] = False
        p = O.plan(REQ, DEMO, reg)
        self.assertTrue(all(st["skill"] in (None,) for st in p["stages"]))
        self.assertTrue(p["rollback"]["allSkillsOffEqualsBaseline"])

    def test_forbidden_shake(self):
        s = by_id(O.plan(REQ, DEMO, REG))
        self.assertIn("no-shake", s["camera-movement"]["mode"])

    def test_deterministic(self):
        self.assertEqual(O.plan(REQ, DEMO, REG), O.plan(REQ, DEMO, REG))


if __name__ == "__main__":
    unittest.main(verbosity=2)
