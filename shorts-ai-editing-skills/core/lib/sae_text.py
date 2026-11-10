"""Unicode text helpers for Vietnamese + English captions (stdlib only).

- NFC normalisation (Vietnamese text from ASR/clipboard is often NFD).
- Approximate grapheme segmentation: base char + combining marks + ZWJ sequences
  + variation selectors + emoji modifiers + regional-indicator pairs. This covers
  Vietnamese fully. For full UAX #29 in JS use Intl.Segmenter; in Python the optional
  `regex` package (\\X). Never use list(str) / str.split('') for animation units.
- Display-width estimate used for line breaking BEFORE the real engine measures text.
  The renderer must re-measure with the real font; this is only a planning heuristic.
"""
from __future__ import annotations

import re
import unicodedata
from typing import List

ZWJ = "‍"
_VS = re.compile(r"[︀-️]")
_PUNCT_TRAIL = set(",.!?;:…)]}\"'»”’%")
_PUNCT_LEAD = set("([{\"'«“‘")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _is_extend(ch: str) -> bool:
    cp = ord(ch)
    return (
        unicodedata.combining(ch) != 0
        or unicodedata.category(ch) in ("Mn", "Me")
        or 0xFE00 <= cp <= 0xFE0F  # variation selectors
        or 0x1F3FB <= cp <= 0x1F3FF  # skin tone modifiers
        or 0xE0020 <= cp <= 0xE007F  # tag chars
    )


def _is_ri(ch: str) -> bool:
    return 0x1F1E6 <= ord(ch) <= 0x1F1FF


def graphemes(s: str) -> List[str]:
    """Approximate extended grapheme clusters (good for VI/EN/common emoji)."""
    s = nfc(s)
    out: List[str] = []
    i = 0
    while i < len(s):
        cl = s[i]
        i += 1
        if cl == "\r" and i < len(s) and s[i] == "\n":
            cl += s[i]
            i += 1
            out.append(cl)
            continue
        if _is_ri(cl) and i < len(s) and _is_ri(s[i]):
            cl += s[i]
            i += 1
        while i < len(s):
            ch = s[i]
            if _is_extend(ch):
                cl += ch
                i += 1
            elif ch == ZWJ and i + 1 < len(s):
                cl += ch + s[i + 1]
                i += 2
            else:
                break
        out.append(cl)
    return out


def tokenize_words(s: str) -> List[str]:
    """Split on whitespace; punctuation stays attached to its word."""
    return [w for w in nfc(s).split() if w]


def strip_punct(word: str) -> str:
    return "".join(ch for ch in word if unicodedata.category(ch)[0] not in ("P", "S")).strip()


def ends_sentence(word: str) -> bool:
    return bool(re.search(r"[.!?…]['\"”’)]*$", word))


def ends_clause(word: str) -> bool:
    return bool(re.search(r"[,;:–—]['\"”’)]*$", word)) or ends_sentence(word)


def display_width(s: str) -> float:
    """Rough width in 'average Latin glyph' units. Uppercase/wide glyphs count more,
    combining marks count 0 (they stack on the base letter)."""
    w = 0.0
    for g in graphemes(s):
        base = g[0]
        if base.isspace():
            w += 0.35
        elif unicodedata.east_asian_width(base) in ("W", "F") or ord(base) >= 0x1F000:
            w += 1.8
        elif base.isupper() or base in "MW@%":
            w += 1.18
        elif base in "il.,;:!'|":
            w += 0.45
        else:
            w += 1.0
    return w


def is_number_like(word: str) -> bool:
    return bool(re.search(r"\d", word))
