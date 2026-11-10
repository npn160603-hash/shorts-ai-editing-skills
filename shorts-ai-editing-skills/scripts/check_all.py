"""Package check: structure, SKILL.md 12 sections, examples vs schemas, no code in JSON, all tests.

    python scripts/check_all.py          # everything (FFmpeg smoke tests skip if ffmpeg absent)
    python scripts/check_all.py --fast   # skip unit tests
Exit code 0 = PASS. This proves the PACKAGE is consistent — not that it is integrated in your editor.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core/lib"))
from sae_schema import load_json, validate  # noqa: E402

PAIRS = [
    ("skills.registry.json", "core/schemas/skill-registry.schema.json"),
    ("core/examples/transcript.example.json", "core/schemas/transcript.schema.json"),
    ("core/examples/capability-manifest.example.json", "core/schemas/capability-manifest.schema.json"),
    ("core/examples/capability-manifest.demo-ffmpeg.json", "core/schemas/capability-manifest.schema.json"),
    ("core/examples/platform-safe-zones.json", "core/schemas/platform-safe-zones.schema.json"),
    ("core/examples/subject-boxes.example.json", "core/schemas/subject-boxes.schema.json"),
    ("orchestrator/examples/edit-request.example.json", "orchestrator/schemas/edit-request.schema.json"),
    ("orchestrator/examples/orchestration-plan.example.json", "orchestrator/schemas/orchestration-plan.schema.json"),
    ("orchestrator/examples/orchestration-plan.demo-ffmpeg.example.json", "orchestrator/schemas/orchestration-plan.schema.json"),
    ("skills/01-editing-director/examples/content-analysis.example.json", "skills/01-editing-director/schemas/content-analysis.schema.json"),
    ("skills/01-editing-director/examples/director-decisions.example.json", "skills/01-editing-director/schemas/director-decisions.schema.json"),
    ("skills/02-smart-captions/examples/caption-track.example.json", "skills/02-smart-captions/schemas/caption-track.schema.json"),
    ("skills/02-smart-captions/examples/caption-style-presets.json", "skills/02-smart-captions/schemas/caption-style-presets.schema.json"),
    ("skills/03-camera-movement/examples/camera-track.example.json", "skills/03-camera-movement/schemas/camera-track.schema.json"),
    ("skills/04-smart-cut-pacing/examples/cut-list.example.json", "skills/04-smart-cut-pacing/schemas/cut-list.schema.json"),
    ("skills/04-smart-cut-pacing/examples/transcript.output-time.example.json", "core/schemas/transcript.schema.json"),
    ("skills/05-advanced-transitions/examples/transition-plan.example.json", "skills/05-advanced-transitions/schemas/transition-plan.schema.json"),
    ("skills/06-cinematic-vfx/examples/vfx-plan.example.json", "skills/06-cinematic-vfx/schemas/vfx-plan.schema.json"),
    ("skills/07-audio-director/examples/audio-mix-plan.example.json", "skills/07-audio-director/schemas/audio-mix-plan.schema.json"),
    ("skills/07-audio-director/examples/sfx-library.example.json", "skills/07-audio-director/schemas/sfx-library.schema.json"),
    ("skills/08-visual-quality-reviewer/examples/qa-report.example.json", "skills/08-visual-quality-reviewer/schemas/qa-report.schema.json"),
]
V11 = ROOT.parent / "shorts-motion-designer/schemas/shorts-motion-plan.schema.json"
CODE_IN_JSON = re.compile(r"(=>|function\s*\(|\beval\s*\(|<script|__import__|\bexec\s*\()")
SKILL_DIRS = ["orchestrator"] + [f"skills/{d.name}" for d in sorted((ROOT / "skills").iterdir()) if d.is_dir()]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    errors = []
    for d in SKILL_DIRS:
        for f in ("SKILL.md", "README.md", "integration-guide.md"):
            if not (ROOT / d / f).is_file():
                errors.append(f"missing {d}/{f}")
        for sub in ("schemas", "examples", "tests", "lib", "references"):
            if not (ROOT / d / sub).is_dir():
                errors.append(f"missing {d}/{sub}/")
        md = (ROOT / d / "SKILL.md").read_text(encoding="utf-8") if (ROOT / d / "SKILL.md").is_file() else ""
        for i in range(1, 13):
            if not re.search(rf"^## {i}\. ", md, re.M):
                errors.append(f"{d}/SKILL.md lacks section '## {i}.'")
        if not md.startswith("---\nname: "):
            errors.append(f"{d}/SKILL.md lacks frontmatter")
    for inst, sch in PAIRS:
        errs = validate(load_json(ROOT / inst), load_json(ROOT / sch))
        errors += [f"{inst}: {e}" for e in errs]
    mp = ROOT / "skills/02-smart-captions/examples/motion-plan.compiled.example.json"
    if V11.is_file():
        errors += [f"motion plan vs V1.1: {e}" for e in validate(load_json(mp), load_json(V11))]
    else:
        print("note: ../shorts-motion-designer not found; V1.1 compatibility check skipped")
    for p in ROOT.rglob("*.json"):
        if "_demo_out" in p.parts:
            continue
        txt = p.read_text(encoding="utf-8")
        try:
            json.loads(txt)
        except json.JSONDecodeError as e:
            errors.append(f"{p.relative_to(ROOT)}: invalid JSON {e}")
        if CODE_IN_JSON.search(txt):
            errors.append(f"{p.relative_to(ROOT)}: looks like executable code inside JSON")
    if "--fast" not in sys.argv:
        tests = sorted(ROOT.glob("**/tests/test_*.py"))
        for t in tests:
            r = subprocess.run([sys.executable, str(t)], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(t.parent),
                               env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
            tail = (r.stderr.strip().splitlines() or ["?"])[-1]
            ran = next((ln for ln in r.stderr.splitlines() if ln.startswith("Ran ")), "")
            print(f"{'OK  ' if r.returncode == 0 else 'FAIL'} {t.relative_to(ROOT)}  {ran}  {tail}")
            if r.returncode != 0:
                errors.append(f"tests failed: {t.relative_to(ROOT)}\n{r.stderr[-2000:]}")
    if errors:
        print("FAIL\n" + "\n".join("- " + e for e in errors))
        return 1
    print("PASS: structure, 12-section SKILL.md files, schemas/examples, no code in JSON, tests."
          "\nThis does NOT prove integration into your editor — follow CODEX_START_HERE.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
