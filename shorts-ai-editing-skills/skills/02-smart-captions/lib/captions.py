"""Skill 02 — Smart Dynamic Captions reference implementation (stdlib only).

build_track()      transcript(output time) + director decisions + style -> CaptionTrack JSON
to_ass()           CaptionTrack -> .ass (libass/FFmpeg `subtitles=` filter) with per-word highlight
to_motion_plan()   CaptionTrack -> ShortsMotionPlan v1.0 (reuses shorts-motion-designer V1.1 schema)

Never invents word timings: per-word highlight only when transcript.wordTimestampsReliable.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "lib"))
from sae_text import display_width, ends_clause, ends_sentence, is_number_like, nfc, strip_punct, tokenize_words  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
CHAR_W = 0.56  # fallback only: average bold-sans glyph width / font size (used when no font file)
import sae_fontmetrics  # noqa: E402
from sae_layout import safe_center_x  # noqa: E402

_FONT = None          # FontMetrics of the active preset (set by build_track); None -> estimate
_MARGIN = 1.0         # 0.97 with real metrics (kerning / side bearings not modelled)


def _em(s: str) -> float:
    """Width of `s` in em units (1.0 = font size)."""
    return _FONT.width_px(s, 1.0) if _FONT else display_width(s) * CHAR_W


def resolve_font(style: Dict):
    f = style.get("fontFile")
    if not f:
        return None
    path = Path(f) if Path(f).is_absolute() else sae_fontmetrics.FONTS_DIR / f
    return sae_fontmetrics.load(str(path)) if path.is_file() else None


def load_presets(path: Optional[Path] = None) -> Dict[str, Dict]:
    data = json.loads((path or HERE / "examples" / "caption-style-presets.json").read_text(encoding="utf-8"))
    return {p["id"]: p for p in data["presets"]}


# ------------------------------------------------------------------ layout helpers
def line_budget(style: Dict, video_w: int, safe: Dict, font_scale: float = 1.0) -> float:
    usable = video_w * (1 - safe["left"] - safe["right"]) * style.get("maxLineWidthRatio", 0.9) * _MARGIN
    return usable / (style["fontSize"] * font_scale)  # budget in em


# Common Vietnamese 2-syllable words: never split across a line or page break.
# Extend per project in references/vi-compounds.txt (one compound per line).
VI_COMPOUNDS = {
    "lãng phí", "thời gian", "thông báo", "làm việc", "tập trung", "khác biệt", "theo dõi", "quan trọng",
    "bí mật", "sai lầm", "miễn phí", "tiết kiệm", "hiệu quả", "kết quả", "nghiên cứu", "công việc", "cuộc sống",
    "sức khỏe", "sức khoẻ", "tiền bạc", "kinh doanh", "khách hàng", "sản phẩm", "dịch vụ", "thị trường", "đầu tư",
    "lợi nhuận", "chia sẻ", "đăng ký", "bình luận", "video", "điện thoại", "máy tính", "ứng dụng", "phần mềm",
    "học tập", "kiến thức", "kinh nghiệm", "thành công", "thất bại", "mục tiêu", "kế hoạch", "thói quen",
    "buổi sáng", "buổi tối", "mỗi ngày", "hôm nay", "ngày mai", "bây giờ", "tại sao", "như thế", "thế nào",
    "bao nhiêu", "đơn giản", "dễ dàng", "nhanh chóng", "chắc chắn", "thật sự", "thực sự", "hoàn toàn",
    "giúp đỡ", "lấy lại", "bắt đầu", "kết thúc", "tiếp tục", "trải nghiệm", "cảm xúc", "gia đình", "bạn bè",
}


def _load_extra_compounds() -> None:
    f = HERE / "references" / "vi-compounds.txt"
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = nfc(line.strip().lower())
            if line and not line.startswith("#"):
                VI_COMPOUNDS.add(line)


_load_extra_compounds()


def _keeps_together(a: str, b: str) -> bool:
    """Do not break between a number and its unit, inside a known compound word,
    or before a lone punctuation token."""
    pa, pb = strip_punct(a), strip_punct(b)
    if not pb:
        return True
    if is_number_like(pa) and not is_number_like(pb):
        return True
    if re.search(r"[,.;:!?…]$", a):
        return False
    return nfc(f"{pa} {pb}".lower()) in VI_COMPOUNDS


def break_cost(a: str, b: str) -> float:
    if ends_sentence(a):
        return -3.0
    if ends_clause(a):
        return -1.5
    return 14.0 if _keeps_together(a, b) else 1.0


def balance_lines(tokens: Sequence[str], budget: float, max_lines: int) -> List[List[int]]:
    """Return token-index lines. 1 line if it fits; otherwise the split minimising the widest
    line, penalising number|unit splits and 1-word orphans."""
    n = len(tokens)
    if n == 0:
        return []
    width = lambda i, j: _em(" ".join(tokens[i:j]))  # noqa: E731
    if width(0, n) <= budget or max_lines == 1 or n == 1:
        return [list(range(n))]
    best: Tuple[float, List[List[int]]] = (float("inf"), [list(range(n))])
    if max_lines >= 2:
        for k in range(1, n):
            w1, w2 = width(0, k), width(k, n)
            cost = max(w1, w2) + (50 if max(w1, w2) > budget else 0)
            cost += break_cost(tokens[k - 1], tokens[k])
            cost += 4 if (k == 1 or n - k == 1) and n > 3 else 0
            cost += 0.15 * abs(w1 - w2)
            if cost < best[0]:
                best = (cost, [list(range(0, k)), list(range(k, n))])
    return best[1]


def _fits(tokens: Sequence[str], budget: float, max_lines: int) -> bool:
    lines = balance_lines(tokens, budget, max_lines)
    return len(lines) <= max_lines and all(_em(" ".join(tokens[i] for i in ln)) <= budget for ln in lines)


# ------------------------------------------------------------------ paging
def _emphasis_for(word: str, keywords: Sequence[str]) -> Optional[str]:
    core = strip_punct(word).lower()
    for k in keywords:
        if core and core in [strip_punct(x).lower() for x in k.split()]:
            return "keyword"
    if is_number_like(core):
        return "number"
    return None


def _page_anim(text: str, mode: str, preset: Dict) -> str:
    if mode == "headline":
        return "hook-reveal"
    if mode == "calm":
        return "fade-in"
    if text.rstrip().endswith("!"):
        return "scale-pop"
    return preset.get("defaultAnimationIn", "soft-slide-up")


def _mode_at(t: float, decisions: Optional[Dict]) -> str:
    if not decisions:
        return "standard"
    for s in decisions["segments"]:
        if s["startSec"] - 1e-3 <= t < s["endSec"] + 1e-3:
            return s["captionMode"]
    return "standard"


def _chunks(words: Sequence[Dict], decisions: Optional[Dict]) -> List[List[Dict]]:
    """Hard boundaries: sentence end, pause > 0.35 s, caption-mode change."""
    out: List[List[Dict]] = []
    cur: List[Dict] = []
    for w in words:
        if cur and (ends_sentence(cur[-1]["text"]) or w["startSec"] - cur[-1]["endSec"] > 0.35
                    or _mode_at(w["startSec"], decisions) != _mode_at(cur[0]["startSec"], decisions)):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def _page_ok(ws: Sequence[Dict], budget: float, style: Dict) -> bool:
    if len(ws) == 1:
        return True
    return (len(ws) <= style.get("maxWordsPerPage", 8)
            and ws[-1]["endSec"] - ws[0]["startSec"] <= style.get("maxPageSec", 2.6)
            and _fits([w["text"] for w in ws], budget, style["maxLines"]))


def partition(ws: Sequence[Dict], budget: float, style: Dict) -> List[List[Dict]]:
    """DP over break positions: fewest, most balanced pages; avoid splitting compounds,
    number+unit and leaving 1-word orphans."""
    n = len(ws)
    INF = float("inf")
    dp = [0.0] + [INF] * n
    back = [0] * (n + 1)
    target = max(1, min(style.get("maxWordsPerPage", 8), n))
    for j in range(1, n + 1):
        for i in range(max(0, j - 14), j):
            if dp[i] == INF or not _page_ok(ws[i:j], budget, style):
                continue
            size = j - i
            c = dp[i] + 10.0 + 0.6 * abs(size - target)
            if size == 1 and n > 2:
                c += 6.0
            if j < n:
                c += break_cost(ws[j - 1]["text"], ws[j]["text"])
            if c < dp[j]:
                dp[j], back[j] = c, i
    pages, j = [], n
    while j > 0:
        pages.append(list(ws[back[j]:j]))
        j = back[j]
    return pages[::-1]


def _pages_from_words(words: Sequence[Dict], budget: float, style: Dict, decisions: Optional[Dict]) -> List[List[Dict]]:
    pages: List[List[Dict]] = []
    for ch in _chunks(words, decisions):
        pages += partition(ch, budget, style)
    return pages


def _pages_from_segments(segments: Sequence[Dict], budget: float, style: Dict) -> List[List[Dict]]:
    """Phrase mode (no reliable word timings). Splits a segment into pages by layout only;
    page times are proportional to characters -> marked timing='estimated-phrase'."""
    pages = []
    for s in segments:
        toks = tokenize_words(s["text"])
        groups, cur = [], []
        for t in toks:
            if cur and (not _fits(cur + [t], budget, style["maxLines"]) or len(cur) >= style.get("maxWordsPerPage", 8)):
                groups.append(cur)
                cur = []
            cur.append(t)
            if ends_clause(t) and _em(" ".join(cur)) > 0.6 * budget:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        total = sum(_em(" ".join(g)) for g in groups) or 1
        t0, span = s["startSec"], s["endSec"] - s["startSec"]
        for g in groups:
            d = span * _em(" ".join(g)) / total
            pages.append([{"text": x, "startSec": t0, "endSec": t0 + d, "_estimated": True} for x in g])
            t0 += d
    return pages


# ------------------------------------------------------------------ placement
def _overlap_ratio(a: Dict, b: Dict) -> float:
    ix = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    iy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    return (ix * iy) / max(a["w"] * a["h"], 1e-9)


def place(t0: float, t1: float, n_lines: int, style: Dict, font_scale: float, video: Dict, safe: Dict,
          subject_boxes: Sequence[Dict], candidates: Sequence[float]) -> Tuple[Dict, List[str]]:
    h = n_lines * style["fontSize"] * font_scale * style.get("lineHeight", 1.2) / video["height"]
    w = 1 - safe["left"] - safe["right"]
    notes = []
    for y in candidates:
        top = max(safe["top"] + h / 2, min(y, 1 - safe["bottom"] - h / 2))
        block = {"x": safe["left"], "y": top - h / 2, "w": w, "h": h}
        hits = [b for b in subject_boxes if b["startSec"] < t1 and t0 < b["endSec"] and _overlap_ratio(block, b["box"]) > 0.15]
        if not hits:
            if y != candidates[0]:
                notes.append(f"moved from y={candidates[0]} to y={y} to avoid subject box")
            return {"x": round(safe_center_x(safe), 4), "y": round(top, 4), "anchor": "center", "blockHeight": round(h, 4)}, notes
    notes.append("no candidate free of subject boxes; kept default and flagged for QA")
    y = candidates[0]
    top = max(safe["top"] + h / 2, min(y, 1 - safe["bottom"] - h / 2))
    return {"x": round(safe_center_x(safe), 4), "y": round(top, 4), "anchor": "center", "blockHeight": round(h, 4)}, notes


# ------------------------------------------------------------------ main builder
def build_track(transcript: Dict, video: Dict, safe: Dict, style_id: str = "clean-bold",
                decisions: Optional[Dict] = None, subject_boxes: Sequence[Dict] = (),
                presets: Optional[Dict[str, Dict]] = None, force_phrase: bool = False) -> Dict:
    if transcript["timebase"] != "output":
        raise ValueError("captions need output-time transcript (run Skill 04 remap, identity if no cuts)")
    global _FONT, _MARGIN
    presets = presets or load_presets()
    style = presets[style_id]
    _FONT = resolve_font(style)
    _MARGIN = 0.97 if _FONT else 1.0
    word_mode = bool(transcript.get("words")) and transcript["wordTimestampsReliable"] and not force_phrase
    words = [dict(w, text=nfc(w["text"])) for w in transcript.get("words", [])] if word_mode else []
    keywords = [a["target"] for a in (decisions or {}).get("accents", []) if a["type"] == "keyword-pop" and a.get("target")]
    budget = line_budget(style, video["width"], safe)
    raw_pages = _pages_from_words(words, budget, style, decisions) if word_mode else \
        _pages_from_segments(transcript["segments"], budget, style)
    pages, warnings = [], []
    for i, pw in enumerate(raw_pages):
        start = pw[0]["startSec"]
        nxt = raw_pages[i + 1][0]["startSec"] if i + 1 < len(raw_pages) else float("inf")
        end = min(pw[-1]["endSec"] + style.get("holdAfterSec", 0.15), nxt)
        if end - start < style.get("minPageSec", 0.5):
            end = min(start + style.get("minPageSec", 0.5), nxt)
        mode = _mode_at(start, decisions)
        font_scale = style.get("headlineScale", 1.2) if mode == "headline" else 1.0
        toks = [w["text"] for w in pw]
        lines = balance_lines(toks, line_budget(style, video["width"], safe, font_scale), style["maxLines"])
        cands = style.get("placementCandidatesY", [0.70, 0.32, 0.80])
        if mode == "headline":
            cands = style.get("headlinePlacementY", [0.30, 0.70])
        placement, notes = place(start, end, len(lines), style, font_scale, video, safe, subject_boxes, cands)
        warnings += [f"page p{i + 1:03d}: {n}" for n in notes]
        text = " ".join(toks)
        page = {
            "id": f"p{i + 1:03d}", "startSec": round(start, 4), "endSec": round(end, 4),
            "captionMode": mode, "fontScale": font_scale,
            "timing": "word" if word_mode else "estimated-phrase",
            "lines": [[int(x) for x in ln] for ln in lines],
            "words": [{"text": w["text"], "startSec": round(w["startSec"], 4), "endSec": round(w["endSec"], 4),
                       **({"emphasis": e} if (e := _emphasis_for(w["text"], keywords)) else {})} for w in pw],
            "placement": placement,
            "animationIn": _page_anim(text, mode, style),
            "animationOut": "cut",
            "cps": round(len(text.replace(" ", "")) / max(end - start, 1e-6), 1),
        }
        if page["cps"] > style.get("maxCps", 17):
            warnings.append(f"page {page['id']}: {page['cps']} chars/s exceeds maxCps {style.get('maxCps', 17)} (speech too fast to read)")
        pages.append(page)
    all_text = " ".join(w["text"] for p in pages for w in p["words"])
    font_check = {"file": Path(_FONT.path).name if _FONT else style.get("fontFile", ""),
                  "metrics": "font-file" if _FONT else "estimate",
                  "missingGlyphs": _FONT.missing(all_text) if _FONT else []}
    if not _FONT:
        warnings.append("font file not found: widths are ESTIMATED; renderer must re-measure")
    if font_check["missingGlyphs"]:
        warnings.append(f"font lacks glyphs {font_check['missingGlyphs']} -> tofu boxes unless the renderer falls back")
    return {
        "captionTrackVersion": "1.0", "timebase": "output", "fontCheck": font_check,
        "mode": "word-highlight" if word_mode else "phrase",
        "language": transcript["language"], "stylePreset": style_id,
        "video": {"width": video["width"], "height": video["height"]}, "safeArea": safe,
        "pages": pages, "warnings": warnings,
    }


# ------------------------------------------------------------------ exporters
def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_color(hex_rgb: str, alpha: int = 0) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_escape(s: str) -> str:
    return s.replace("\\", "∖").replace("{", "(").replace("}", ")")


def to_ass(track: Dict, presets: Optional[Dict[str, Dict]] = None) -> str:
    st = (presets or load_presets())[track["stylePreset"]]
    W, H = track["video"]["width"], track["video"]["height"]
    boxed = st.get("box", False)
    fm = resolve_font(st)
    # preset fontSize = em size in px (CSS/Canvas meaning). libass sizes by winAscent+winDescent,
    # so convert to keep preview (CSS) and export (ASS) the same visual size.
    ass_size = round(fm.ass_size_for_em(st["fontSize"]), 1) if fm else st["fontSize"]
    header = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Cap,{font},{size},{pri},{pri},{out},{back},{bold},0,0,0,100,100,{sp},0,{bs},{ol},{sh},5,0,0,0,1".format(
            font=st["fontFamily"], size=ass_size, pri=_ass_color(st["fill"]), out=_ass_color(st["stroke"]),
            back=_ass_color(st.get("boxColor", "#000000"), st.get("boxAlpha", 128)), bold=-1 if st.get("bold", True) else 0,
            sp=st.get("letterSpacing", 0), bs=3 if boxed else 1, ol=st.get("boxPadding", 12) if boxed else st["strokeWidth"],
            sh=0 if boxed else st.get("shadow", 2)),
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    hi = _ass_color(st["highlightColor"])
    kw = _ass_color(st.get("keywordColor", st["highlightColor"]))
    events = []
    for p in track["pages"]:
        x, y = int(round(p["placement"]["x"] * W)), int(round(p["placement"]["y"] * H))
        scale = int(round(100 * p.get("fontScale", 1.0)))
        tw = [_ass_escape(w["text"]) for w in p["words"]]
        if st.get("uppercase"):
            tw = [t.upper() for t in tw]

        def render(active: Optional[int]) -> str:
            out_lines = []
            for ln in p["lines"]:
                parts = []
                for i in ln:
                    w, t = p["words"][i], tw[i]
                    if i == active and track["mode"] == "word-highlight":
                        pop = st.get("activeWordScale", 1.0) * (st.get("keywordScale", 1.0) if w.get("emphasis") else 1.0)
                        sc = int(round(scale * pop))
                        parts.append(f"{{\\c{hi}\\fscx{sc}\\fscy{sc}}}{t}{{\\c{_ass_color(st['fill'])}\\fscx{scale}\\fscy{scale}}}")
                    elif w.get("emphasis") in ("keyword", "number") and st.get("colorKeywords", True):
                        parts.append(f"{{\\c{kw}}}{t}{{\\c{_ass_color(st['fill'])}}}")
                    else:
                        parts.append(t)
                out_lines.append(" ".join(parts))
            return "\\N".join(out_lines)

        base = f"{{\\an5\\pos({x},{y})\\fscx{scale}\\fscy{scale}}}"
        anim = p["animationIn"]
        if anim in ("scale-pop", "hook-reveal"):
            s0 = int(round(scale * (0.85 if anim == "hook-reveal" else 0.9)))
            over = int(round(scale * 1.05))  # back-out overshoot: s0 -> 105% -> 100%
            intro = (f"{{\\fscx{s0}\\fscy{s0}\\t(0,110,\\fscx{over}\\fscy{over})"
                     f"\\t(110,190,\\fscx{scale}\\fscy{scale})\\fad(90,0)}}")
        elif anim == "soft-slide-up":
            dy = int(round(0.012 * H))
            intro = f"{{\\move({x},{y + dy},{x},{y},0,160)\\fad(110,0)}}"
        else:
            intro = "{\\fad(160,0)}"
        if track["mode"] == "word-highlight":
            n = len(p["words"])
            for i, w in enumerate(p["words"]):
                a = p["startSec"] if i == 0 else w["startSec"]
                b = p["words"][i + 1]["startSec"] if i + 1 < n else p["endSec"]
                if b - a < 0.01:
                    continue
                txt = base + (intro if i == 0 else "") + render(i)
                events.append(f"Dialogue: 1,{_ass_time(a)},{_ass_time(b)},Cap,,0,0,0,,{txt}")
        else:
            events.append(f"Dialogue: 1,{_ass_time(p['startSec'])},{_ass_time(p['endSec'])},Cap,,0,0,0,,{base}{intro}{render(None)}")
    return "\n".join(header + events) + "\n"


def to_motion_plan(track: Dict, fps: float, duration: float, presets: Optional[Dict[str, Dict]] = None,
                   keyword_callouts: Sequence[Dict] = ()) -> Dict:
    """Phrase-level compile into the existing ShortsMotionPlan v1.0 (shorts-motion-designer V1.1).
    Per-word highlight is NOT representable in v1.0 -> use to_ass() or a native adapter for that."""
    st = (presets or load_presets())[track["stylePreset"]]
    cues, elements = [], []
    for p in track["pages"]:
        text = " ".join(w["text"] for w in p["words"])
        cues.append({"startSec": p["startSec"], "endSec": p["endSec"], "text": text,
                     "emphasis": any("emphasis" in w for w in p["words"]),
                     "source": "aligned-word" if p["timing"] == "word" else "transcript-phrase"})
        y = p["placement"]["y"]
        anims = [{"property": "opacity", "from": 0, "to": 1, "startSec": p["startSec"], "durationSec": 0.16, "easing": "ease-out"}]
        if p["animationIn"] == "soft-slide-up":
            anims.append({"property": "position.y", "from": round(min(1.0, y + 0.012), 4), "to": y,
                          "startSec": p["startSec"], "durationSec": 0.16, "easing": "ease-out"})
        elif p["animationIn"] in ("scale-pop", "hook-reveal"):
            anims.append({"property": "scale", "from": 0.88, "to": 1, "startSec": p["startSec"], "durationSec": 0.14, "easing": "ease-out"})
        elements.append({"id": f"cap-{p['id']}", "kind": "text", "text": text.upper() if st.get("uppercase") else text,
                         "startSec": p["startSec"], "endSec": p["endSec"], "zIndex": 40,
                         "position": {"x": p["placement"]["x"], "y": y},
                         "styles": {"fontFamily": st["fontFamily"], "fontSize": round(st["fontSize"] * p.get("fontScale", 1.0)),
                                    "fontWeight": "bold" if st.get("bold", True) else "normal", "fill": st["fill"],
                                    "stroke": st["stroke"], "strokeWidth": st["strokeWidth"], "maxLines": st["maxLines"]},
                         "animations": anims})
    for i, k in enumerate(keyword_callouts):
        a, d = k["atSec"], min(k.get("durationSec", 0.8), max(0.2, duration - k["atSec"]))
        elements.append({"id": f"kw-{i + 1:02d}", "kind": "text", "text": k["target"].upper(),
                         "startSec": round(a, 4), "endSec": round(a + d, 4), "zIndex": 45,
                         "position": {"x": 0.5, "y": 0.24},
                         "styles": {"fontFamily": st["fontFamily"], "fontSize": round(st["fontSize"] * 1.35),
                                    "fontWeight": "bold", "fill": st["highlightColor"], "stroke": st["stroke"], "strokeWidth": st["strokeWidth"]},
                         "animations": [{"property": "scale", "from": 0.82, "to": 1, "startSec": round(a, 4), "durationSec": 0.16, "easing": "ease-out"},
                                        {"property": "opacity", "from": 0, "to": 1, "startSec": round(a, 4), "durationSec": 0.1, "easing": "ease-out"}]})
    return {"version": "1.0",
            "video": {"width": track["video"]["width"], "height": track["video"]["height"], "fps": fps, "durationSec": duration},
            "safeArea": track["safeArea"], "cues": cues, "elements": elements}


def ffmpeg_subtitles_filter(ass_path: str, fonts_dir: Optional[str] = None) -> str:
    """`subtitles=` filter with a path escaped for FFmpeg filtergraph syntax (Windows-safe:
    'C:\\x\\c.ass' -> 'C\\:/x/c.ass')."""
    def esc(p: str) -> str:
        p = str(p).replace("\\", "/")
        return "'" + p.replace(":", "\\:").replace("'", "\\'") + "'"
    f = f"subtitles=filename={esc(ass_path)}"
    if fonts_dir:
        f += f":fontsdir={esc(fonts_dir)}"
    return f
