import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import sae_testutil as U  # noqa: E402

INST = [sys.executable, str(ROOT / "scripts" / "install_opencode.py")]


class TestInstall(unittest.TestCase):
    def test_install_layout_and_non_destructive(self):
        ws = U.tmpdir()
        (ws / "opencode.json").write_text('{"model": "mine"}', encoding="utf-8")
        r = subprocess.run(INST + [str(ws)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        sk = ws / ".opencode" / "skills" / "shorts-ai-editing-skills"
        self.assertTrue((sk / "AGENTS.md").is_file())
        self.assertTrue((ws / ".opencode" / "commands" / "shorts.md").is_file())
        self.assertEqual(json.loads((ws / "opencode.json").read_text(encoding="utf-8")), {"model": "mine"})  # untouched
        self.assertIn("NOT modified", r.stdout)
        # OpenCode discovery: every skill dir has SKILL.md; package root itself has none (else it would hide the others)
        self.assertFalse((sk / "SKILL.md").exists())
        found = sorted(p.parent.name for p in (ws / ".opencode" / "skills").rglob("SKILL.md"))
        self.assertIn("orchestrator", found)
        self.assertEqual(len([f for f in found if f[:2].isdigit()]), 8)
        self.assertFalse(any("_demo_out" in str(p) for p in sk.rglob("*")))
        r2 = subprocess.run(INST + [str(ws)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r2.returncode, 2)  # refuses to overwrite


if __name__ == "__main__":
    unittest.main(verbosity=2)
