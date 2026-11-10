"""Measure text width from a TrueType/OpenType (glyf or CFF) font — Python stdlib only.

Reads `head` (unitsPerEm), `hhea` + `hmtx` (advance widths) and `cmap` (format 4 / 12).
Width = sum of glyph advances (combining marks have their own advance, usually 0) + letter
spacing. Kerning/shaping are ignored, so libass/HarfBuzz results can differ by ~1–3 %:
callers keep a safety margin (captions use 0.97 of the usable width).
"""
from __future__ import annotations

import struct
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

FONTS_DIR = Path(__file__).resolve().parents[1] / "fonts"


class FontMetrics:
    def __init__(self, path) -> None:
        self.path = str(path)
        data = Path(path).read_bytes()
        self._data = data
        num = struct.unpack(">H", data[4:6])[0]
        self.tables: Dict[str, tuple] = {}
        for i in range(num):
            tag, _cs, off, ln = struct.unpack(">4sLLL", data[12 + 16 * i: 28 + 16 * i])
            self.tables[tag.decode("latin-1")] = (off, ln)
        self.units_per_em = struct.unpack(">H", self._tab("head")[18:20])[0]
        hhea = self._tab("hhea")
        self.ascender, self.descender = struct.unpack(">hh", hhea[4:8])
        n_hm = struct.unpack(">H", hhea[34:36])[0]
        hmtx = self._tab("hmtx")
        self.advances = [struct.unpack(">H", hmtx[4 * i: 4 * i + 2])[0] for i in range(n_hm)]
        self.cmap = self._read_cmap()
        if "OS/2" in self.tables:
            os2 = self._tab("OS/2")
            self.win_ascent, self.win_descent = struct.unpack(">HH", os2[74:78])
        else:
            self.win_ascent, self.win_descent = self.ascender, -self.descender

    def _tab(self, tag: str) -> bytes:
        off, ln = self.tables[tag]
        return self._data[off: off + ln]

    def _read_cmap(self) -> Dict[int, int]:
        cm = self._tab("cmap")
        n = struct.unpack(">H", cm[2:4])[0]
        subs = []
        for i in range(n):
            pid, eid, off = struct.unpack(">HHL", cm[4 + 8 * i: 12 + 8 * i])
            fmt = struct.unpack(">H", cm[off: off + 2])[0]
            subs.append((fmt, pid, eid, off))
        # prefer full-Unicode format 12, then BMP format 4
        for want in (12, 4):
            for fmt, pid, eid, off in subs:
                if fmt == want and (pid == 0 or (pid == 3 and eid in (1, 10))):
                    return self._fmt12(cm, off) if fmt == 12 else self._fmt4(cm, off)
        raise ValueError("no usable Unicode cmap (format 4/12)")

    @staticmethod
    def _fmt4(cm: bytes, off: int) -> Dict[int, int]:
        segx2 = struct.unpack(">H", cm[off + 6: off + 8])[0]
        n = segx2 // 2
        ends = struct.unpack(f">{n}H", cm[off + 14: off + 14 + segx2])
        p = off + 16 + segx2
        starts = struct.unpack(f">{n}H", cm[p: p + segx2])
        deltas = struct.unpack(f">{n}h", cm[p + segx2: p + 2 * segx2])
        ro_pos = p + 2 * segx2
        ros = struct.unpack(f">{n}H", cm[ro_pos: ro_pos + segx2])
        out = {}
        for i in range(n):
            for c in range(starts[i], ends[i] + 1):
                if c == 0xFFFF:
                    continue
                if ros[i] == 0:
                    g = (c + deltas[i]) & 0xFFFF
                else:
                    gi = ro_pos + 2 * i + ros[i] + 2 * (c - starts[i])
                    g = struct.unpack(">H", cm[gi: gi + 2])[0]
                    if g:
                        g = (g + deltas[i]) & 0xFFFF
                if g:
                    out[c] = g
        return out

    @staticmethod
    def _fmt12(cm: bytes, off: int) -> Dict[int, int]:
        ngroups = struct.unpack(">L", cm[off + 12: off + 16])[0]
        out = {}
        for i in range(ngroups):
            s, e, g = struct.unpack(">LLL", cm[off + 16 + 12 * i: off + 28 + 12 * i])
            for k, c in enumerate(range(s, e + 1)):
                out[c] = g + k
        return out

    def ass_size_for_em(self, em_px: float) -> float:
        """ASS `Fontsize` that renders glyphs at `em_px` (libass scales by winAscent+winDescent;
        verified against libass/FFmpeg 6.1 to within ~1.5 %)."""
        return em_px * (self.win_ascent + self.win_descent) / self.units_per_em

    def has_glyph(self, ch: str) -> bool:
        return ord(ch) in self.cmap

    def missing(self, text: str):
        """Characters that would render as tofu (no glyph), excluding whitespace/controls."""
        t = unicodedata.normalize("NFC", text)
        return sorted({c for c in t if not c.isspace() and unicodedata.category(c)[0] != "C" and not self.has_glyph(c)})

    def advance(self, ch: str) -> int:
        g = self.cmap.get(ord(ch), 0)
        return self.advances[min(g, len(self.advances) - 1)]

    def width_px(self, text: str, size_px: float, letter_spacing_px: float = 0.0) -> float:
        t = unicodedata.normalize("NFC", text)
        units = sum(self.advance(c) for c in t)
        spacing = letter_spacing_px * max(0, len(t) - 1)
        return units * size_px / self.units_per_em + spacing


@lru_cache(maxsize=16)
def load(path: Optional[str] = None) -> FontMetrics:
    return FontMetrics(path or FONTS_DIR / "BeVietnamPro-Bold.ttf")
