import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import sae_env  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

CLI = [sys.executable, str(ROOT / "scripts" / "shorts.py")]
TR = str(ROOT / "core/examples/transcript.example.json")


def run(args, **kw):
    return subprocess.run(CLI + args, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


class TestEnv(unittest.TestCase):
    def test_manifest_valid(self):
        m = sae_env.build_manifest()
        m.pop("_facts")
        self.assertEqual(validate(m, load_json(ROOT / "core/schemas/capability-manifest.schema.json")), [])


class TestCli(unittest.TestCase):
    def test_missing_input_and_transcript(self):
        d = U.tmpdir()
        self.assertEqual(run(["edit", str(d / "nope.mp4")]).returncode, 2)
        if U.HAVE_FFMPEG:
            src = U.make_source(d / "a.mp4", 2.0)
            r = run(["edit", str(src), "--asr", "none"])
            self.assertEqual(r.returncode, 2)
            self.assertIn("transcript", r.stderr.lower())
            st = json.loads(run(["status", str(d / "a_shorts")]).stdout)
            self.assertEqual(st["state"], "failed")

    def test_unlicensed_music_refused(self):
        if not U.HAVE_FFMPEG:
            self.skipTest("ffmpeg")
        d = U.tmpdir()
        src = U.make_source(d / "a.mp4", 2.0)
        r = run(["edit", str(src), "--transcript", TR, "--music", str(src)])
        self.assertEqual(r.returncode, 2)
        self.assertIn("license", r.stderr)

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_detach_status_and_no_overwrite(self):
        d = U.tmpdir()
        src = U.make_source(d / "talk.mp4", 17.0)
        before = (d / "talk.mp4").stat().st_mtime
        r = run(["edit", str(src), "--transcript", TR, "--detach", "--max-revisions", "0"])
        self.assertEqual(r.returncode, 0, r.stderr)
        info = json.loads(r.stdout)
        st = {}
        for _ in range(120):
            time.sleep(1)
            st = json.loads(run(["status", info["project"]]).stdout)
            if st["state"] in ("done", "failed"):
                break
        self.assertEqual(st["state"], "done", st)
        self.assertTrue(Path(st["final"]["path"]).is_file())
        self.assertEqual((d / "talk.mp4").stat().st_mtime, before)
        r2 = run(["edit", str(src), "--max-revisions", "0", "--no-export"])  # cached transcript, new revision
        self.assertIn(r2.returncode, (0, 3), r2.stderr)
        self.assertTrue((Path(info["project"]) / "ai-edit" / "rev-2").is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
