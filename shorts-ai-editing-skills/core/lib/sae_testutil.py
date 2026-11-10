"""Tiny helpers for the FFmpeg smoke tests (stdlib only). Tests skip when ffmpeg is absent."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError("command failed: " + " ".join(cmd)[:300] + "\n" + r.stderr[-1200:])
    return r


def tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="sae_test_"))


def make_source(path: Path, dur: float = 4.0, w: int = 1080, h: int = 1920, fps: int = 30) -> Path:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate={fps}:duration={dur}",
         "-f", "lavfi", "-i", f"sine=frequency=330:duration={dur}", "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)])
    return path


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(path)]).stdout
    return json.loads(out)


def frame_rgb(path: Path, t: float, w: int = 54, h: int = 96) -> bytes:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t}", "-i", str(path), "-frames:v", "1",
                        "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return r.stdout


def mean_abs_diff(a: bytes, b: bytes) -> float:
    n = min(len(a), len(b))
    return sum(abs(a[i] - b[i]) for i in range(n)) / max(n, 1)


def run_bytes(cmd: List[str]) -> bytes:
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise AssertionError("command failed: " + " ".join(cmd)[:300] + "\n" + r.stderr.decode("utf-8", "replace")[-1200:])
    return r.stdout
