"""Timebase helpers shared by all skills (stdlib only).

Contract (extends shorts-motion-designer docs/02-timeline-contract.md):
- Interchange times are float seconds.
- `timebase: "source"` = seconds in the original media; `"output"` = seconds after cuts.
- Only Skill 04 (cut list) converts source -> output. Every later skill works in output time.
- Frame quantization: frame = round(t * fps). Ranges are half-open [start, end).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

EPS = 1e-6


def to_frame(t: float, fps: float) -> int:
    return int(round(t * fps))


def frame_to_sec(n: int, fps: float) -> float:
    return n / fps


def snap(t: float, fps: float) -> float:
    """Snap a time to the nearest frame boundary of `fps`."""
    return round(t * fps) / fps


def merge_ranges(ranges: Iterable[Tuple[float, float]], gap: float = 0.0) -> List[Tuple[float, float]]:
    """Merge overlapping/adjacent ranges (gap <= `gap` seconds are bridged)."""
    rs = sorted((a, b) for a, b in ranges if b - a > EPS)
    out: List[List[float]] = []
    for a, b in rs:
        if out and a <= out[-1][1] + gap + EPS:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def invert_ranges(ranges: Sequence[Tuple[float, float]], total: float) -> List[Tuple[float, float]]:
    """Complement of ranges inside [0, total)."""
    out, cur = [], 0.0
    for a, b in merge_ranges(ranges):
        if a > cur + EPS:
            out.append((cur, min(a, total)))
        cur = max(cur, b)
    if cur < total - EPS:
        out.append((cur, total))
    return out


@dataclass(frozen=True)
class KeepSegment:
    src_start: float
    src_end: float
    out_start: float

    @property
    def out_end(self) -> float:
        return self.out_start + (self.src_end - self.src_start)


def build_keep_map(keeps: Sequence[Tuple[float, float]]) -> List[KeepSegment]:
    """Sorted, non-overlapping source keep ranges -> output offsets (no reorder)."""
    segs, cursor = [], 0.0
    prev_end = -1.0
    for a, b in keeps:
        if b - a <= EPS:
            raise ValueError(f"empty keep range {(a, b)}")
        if a < prev_end - EPS:
            raise ValueError("keep ranges must be sorted and non-overlapping")
        segs.append(KeepSegment(a, b, cursor))
        cursor += b - a
        prev_end = b
    return segs


def keep_map_from_cutlist(cut_list: Dict) -> List[KeepSegment]:
    """Accepts a cut-list JSON (Skill 04 schema). Honors explicit `outStartSec` (reorder)."""
    segs = []
    cursor = 0.0
    for s in cut_list["segments"]:
        out_start = s.get("outStartSec", cursor)
        segs.append(KeepSegment(s["srcStartSec"], s["srcEndSec"], out_start))
        cursor = out_start + (s["srcEndSec"] - s["srcStartSec"])
    return segs


def src_to_out(t: float, segs: Sequence[KeepSegment]) -> Optional[float]:
    """Map a source time to output time; None if `t` falls in a removed region."""
    for s in segs:
        if s.src_start - EPS <= t < s.src_end + EPS:
            return s.out_start + (t - s.src_start)
    return None


def remap_range(a: float, b: float, segs: Sequence[KeepSegment], min_keep_ratio: float = 0.5
                ) -> Optional[Tuple[float, float]]:
    """Map a source range to output. Partially-cut ranges are clipped to the largest kept
    piece; dropped if that piece is < min_keep_ratio of the original duration."""
    best = None
    for s in segs:
        lo, hi = max(a, s.src_start), min(b, s.src_end)
        if hi - lo > EPS and (best is None or hi - lo > best[1] - best[0]):
            best = (lo, hi, s)
    if best is None:
        return None
    lo, hi, s = best
    if (hi - lo) < min_keep_ratio * max(b - a, EPS):
        return None
    return (s.out_start + lo - s.src_start, s.out_start + hi - s.src_start)


def remap_words(words: Sequence[Dict], segs: Sequence[KeepSegment]) -> List[Dict]:
    """Remap word dicts {text,startSec,endSec,...} from source to output time.
    Words removed by cuts are dropped (never invented)."""
    out = []
    for w in words:
        r = remap_range(w["startSec"], w["endSec"], segs)
        if r is None:
            continue
        nw = dict(w)
        nw["startSec"], nw["endSec"] = round(r[0], 4), round(r[1], 4)
        out.append(nw)
    return out


def output_duration(segs: Sequence[KeepSegment]) -> float:
    return max((s.out_end for s in segs), default=0.0)


def overlaps(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    return a[0] < b[1] - EPS and b[0] < a[1] - EPS
