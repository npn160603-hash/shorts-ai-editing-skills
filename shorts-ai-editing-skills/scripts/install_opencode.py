"""Install this package into an OpenCode workspace (non-destructive).

    python scripts/install_opencode.py "D:\\Videos\\MyChannel"          # project install
    python scripts/install_opencode.py --global                          # ~/.config/opencode

Copies the package to <workspace>/.opencode/skills/shorts-ai-editing-skills (refuses if present),
copies /shorts and /shorts-status commands to .opencode/commands/ (skips files that exist),
and creates opencode.json ONLY if none exists — otherwise prints the snippet to merge by hand.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns("_demo_out", "__pycache__", "*.pyc", "doctor-report.json")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", nargs="?")
    ap.add_argument("--global", dest="glob", action="store_true")
    a = ap.parse_args()
    if a.glob:
        base = Path.home() / ".config" / "opencode"
        skills, cmds, cfg = base / "skills", base / "commands", base / "opencode.json"
        instr = str((skills / "shorts-ai-editing-skills" / "AGENTS.md").as_posix())
    elif a.workspace:
        ws = Path(a.workspace).resolve()
        if not ws.is_dir():
            print(f"workspace not found: {ws}")
            return 2
        skills, cmds, cfg = ws / ".opencode" / "skills", ws / ".opencode" / "commands", ws / "opencode.json"
        instr = ".opencode/skills/shorts-ai-editing-skills/AGENTS.md"
    else:
        ap.print_help()
        return 2
    dest = skills / "shorts-ai-editing-skills"
    if dest.exists():
        print(f"already installed: {dest} (not overwritten). Remove it yourself to reinstall.")
        return 2
    skills.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT, dest, ignore=IGNORE)
    v11 = ROOT.parent / "shorts-motion-designer"
    if v11.is_dir() and not (skills / "shorts-motion-designer").exists():
        shutil.copytree(v11, skills / "shorts-motion-designer", ignore=IGNORE)
        print(f"copied Shorts Motion Designer V1.1 -> {skills / 'shorts-motion-designer'}")
    print(f"installed -> {dest}")
    cmds.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "opencode" / "commands").glob("*.md"):
        t = cmds / f.name
        if t.exists():
            print(f"skip existing command {t}")
        else:
            txt = f.read_text(encoding="utf-8")
            if a.glob:
                txt = txt.replace(".opencode/skills/shorts-ai-editing-skills", str(dest.as_posix()))
            t.write_text(txt, encoding="utf-8")
            print(f"command /{f.stem} -> {t}")
    snippet = {"$schema": "https://opencode.ai/config.json", "instructions": [instr], "permission": {"skill": {"*": "allow"}}}
    if cfg.exists():
        print(f"\n{cfg} already exists — NOT modified. Merge these keys by hand:\n" + json.dumps(snippet, indent=2))
    else:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps(snippet, indent=2) + "\n", encoding="utf-8")
        print(f"created {cfg}")
    print(f'\nNext: python "{dest / "scripts" / "doctor.py"}"   then in OpenCode:  /shorts dựng video.mp4 theo phong cách Shorts')
    return 0


if __name__ == "__main__":
    sys.exit(main())
