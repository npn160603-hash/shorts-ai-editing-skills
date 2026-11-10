import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "lib"), str(ROOT / "core" / "lib")]
import audio_mix as A  # noqa: E402
import sae_testutil as U  # noqa: E402
from sae_schema import load_json, validate  # noqa: E402

CAPS = {k: "implemented" for k in ["audio.loudnorm", "audio.duck", "audio.mixSfx", "audio.crossfade", "audio.denoise"]}
LIB = load_json(HERE / "examples/sfx-library.example.json")
MUSIC = {"file": "m.wav", "license": "own", "licenseProof": "test"}
SPEECH = [(0.5, 2.0), (2.3, 3.0), (5.0, 6.0)]


class TestAudio(unittest.TestCase):
    def test_schema(self):
        p = A.build_plan(8.0, SPEECH, CAPS, music=MUSIC, sfx_lib=LIB, anchors=[{"type": "transition", "atSec": 4.0, "ref": "1"}])
        self.assertEqual(validate(p, load_json(HERE / "schemas/audio-mix-plan.schema.json")), [])
        self.assertEqual(validate(LIB, load_json(HERE / "schemas/sfx-library.schema.json")), [])

    def test_unlicensed_music_rejected(self):
        p = A.build_plan(8.0, SPEECH, CAPS, music={"file": "x.mp3", "license": "unknown", "licenseProof": ""})
        self.assertIsNone(p["music"])
        self.assertTrue(any("license" in w for w in p["warnings"]))

    def test_unlicensed_sfx_not_used(self):
        lib = {"libraryVersion": "1.0", "items": [{"id": "x", "category": "whoosh", "file": "x.wav", "durationSec": 0.3, "license": "unknown", "licenseProof": ""}]}
        ev, notes = A.place_sfx([{"type": "transition", "atSec": 2.0}], lib, [], 8.0)
        self.assertEqual(ev, [])

    def test_duck_gain(self):
        sp = A.merge_speech(SPEECH)
        self.assertEqual(sp, [(0.5, 3.0), (5.0, 6.0)])
        g_mid = A.duck_gain_at(1.5, sp, -12, 0.25, 0.45)
        self.assertAlmostEqual(g_mid, 10 ** (-12 / 20), places=4)
        self.assertAlmostEqual(A.duck_gain_at(4.2, sp, -12, 0.25, 0.45), 1.0)
        self.assertLess(A.duck_gain_at(0.4, sp, -12, 0.25, 0.45), 1.0)  # ramps BEFORE speech starts

    def test_sfx_gain_under_speech(self):
        ev, _ = A.place_sfx([{"type": "keyword-pop", "atSec": 1.0}], LIB, A.merge_speech(SPEECH), 8.0)
        self.assertLessEqual(ev[0]["gainDb"], -12)

    def test_bpm_synthetic(self):
        sr, bpm = 11025, 120.0
        n = int(sr * 12)
        x = [0.0] * n
        period = int(sr * 60 / bpm)
        for k in range(0, n, period):
            for j in range(min(300, n - k)):
                x[k + j] = 0.8 * (1 - j / 300)
        got, off, conf = A.estimate_bpm(x, sr)
        self.assertLess(abs(got - bpm), 1.0)

    def test_loudnorm_parse(self):
        txt = 'junk\n{\n "input_i" : "-21.87",\n "input_tp" : "-13.50",\n "input_lra" : "1.10",\n "input_thresh" : "-31.97",\n' \
              ' "output_i" : "-14.0", "output_tp": "-1.0", "output_lra": "1.0", "output_thresh": "-24.0",\n "normalization_type" : "dynamic",\n "target_offset" : "0.12"\n}\n'
        m = A.parse_loudnorm_json(txt)
        self.assertEqual(m["input_i"], -21.87)
        self.assertIn("measured_I=-21.87", A.loudnorm_pass2(m, A.TARGETS["shorts"]))

    @unittest.skipUnless(U.HAVE_FFMPEG, "ffmpeg not installed")
    def test_mix_hits_target(self):
        d = U.tmpdir()
        src = U.make_source(d / "src.mp4", 8.0)
        music = d / "m.wav"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=10", str(music)])
        pop = d / "p.wav"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=900:d=0.12", str(pop)])
        plan = A.build_plan(8.0, SPEECH, CAPS, music=MUSIC, sfx_lib=LIB, anchors=[{"type": "keyword-pop", "atSec": 4.0, "ref": "k"}])
        ins = ["-i", str(src), "-stream_loop", "-1", "-i", str(music)] + sum((["-i", str(pop)] for _ in plan["sfx"]), [])
        pre = d / "pre.wav"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", *ins, "-filter_complex", A.ffmpeg_mix_graph(plan), "-map", "[amix]", "-t", "8", str(pre)])
        import subprocess
        meas = A.parse_loudnorm_json(subprocess.run(A.measure_cmd(str(pre), plan["targets"]), capture_output=True, text=True, encoding="utf-8", errors="replace").stderr)
        out = d / "o.mp4"
        U.run(["ffmpeg", "-hide_banner", "-loglevel", "error", *ins, "-filter_complex", A.ffmpeg_mix_graph(plan, meas),
               "-map", "0:v", "-map", "[amix]", "-c:v", "copy", "-c:a", "aac", "-t", "8", str(out)])
        after = A.parse_loudnorm_json(subprocess.run(A.measure_cmd(str(out), plan["targets"]), capture_output=True, text=True, encoding="utf-8", errors="replace").stderr)
        self.assertLess(abs(after["input_i"] - (-14.0)), 1.0)
        self.assertLessEqual(after["input_tp"], -0.7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
