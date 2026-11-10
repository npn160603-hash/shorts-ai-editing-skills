"""Publish kit: title/description/hashtag suggestions + cover image, from the transcript (no AI needed).

Suggestions reuse the speaker's own words (hook sentence, keywords); an optional LLM adds ideas
that are labelled as such. The cover is the sharpest representative frame of the hook (FFmpeg
`thumbnail` filter) with the chosen title burnt in using the bundled font.
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

import captions as C
import director as D

GENERIC = {"tiktok": ["#fyp", "#xuhuong"], "youtube-shorts": ["#shorts"], "instagram-reels": ["#reels"], "facebook-reels": ["#reels"]}


def _tag(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return f"#{s}" if 3 <= len(s) <= 30 and not s[0].isdigit() else ""


def _cap(s: str) -> str:
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def _cut(s: str, n: int = 70) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    return s[: s.rfind(" ", 0, n - 1)].rstrip(",;:") + "…"


def suggest(transcript: Dict, decisions: Optional[Dict], platforms: List[str], llm_titles: Optional[List[str]] = None,
            credits: Optional[List[Dict]] = None) -> Dict:
    segs = [dict(s, text=_cap(s["text"])) for s in transcript["segments"]]
    hook = segs[0]["text"].strip() if segs else ""
    kws: List[str] = []
    for s in segs:
        for k in D.keyword_candidates(s["text"]):
            if k not in kws:
                kws.append(k)
    titles = []
    if hook:
        titles.append(_cut(hook))
    if len(segs) > 1:
        titles.append(_cut(" ".join(x["text"].strip() for x in segs[:2])))
    if len(kws) >= 2:
        titles.append(_cut(f"{_cap(kws[0])} · {_cap(kws[1])}"))
    titles = list(dict.fromkeys(t for t in titles if t))
    tags = []
    for k in kws:
        t = _tag(k)
        if t and t not in tags:
            tags.append(t)
    for p in platforms:
        for g in GENERIC.get(p, []):
            if g not in tags:
                tags.append(g)
    desc = " ".join(s["text"].strip() for s in segs[:3])
    if credits:
        srcs = sorted({f"{c['source']}{(' / ' + c['author']) if c.get('author') else ''}" for c in credits})
        desc += "\n\nFootage: " + "; ".join(srcs)
    return {"publishVersion": "1.0", "titles": titles[:3], "llmTitles": llm_titles or [], "description": desc[:4500],
            "hashtags": tags[:10], "note": "Gợi ý dựa trên lời nói trong video; kiểm tra lại trước khi đăng."}


def make_cover(video: str, title: str, out_dir: Path, track_style: str = "clean-bold", window: float = 3.0) -> Dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "cover.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-t", f"{window}", "-i", video,
                    "-vf", "thumbnail=60", "-frames:v", "1", "-q:v", "2", str(raw)], check=True)
    st = C.load_presets()[track_style]
    fm = C.resolve_font(st)
    size = round(fm.ass_size_for_em(96), 1) if fm else 96
    ass = out_dir / "_cover.ass"
    ass.write_text("\n".join([
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: T,{st['fontFamily']},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,8,4,5,90,90,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,0:00:00.00,0:00:05.00,T,,0,0,0,,{{\\an5\\pos(540,600)}}{C._ass_escape(title.upper())}", ""]), encoding="utf-8")
    titled = out_dir / "cover_title.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(raw), "-vf",
                    f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                    f"{C.ffmpeg_subtitles_filter(str(ass), str(C.sae_fontmetrics.FONTS_DIR))}", "-q:v", "2", str(titled)], check=True)
    ass.unlink(missing_ok=True)
    return {"cover": str(raw), "coverWithTitle": str(titled)}


def write_kit(out_dir: Path, kit: Dict) -> Path:
    (out_dir / "publish.json").write_text(json.dumps(kit, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Gợi ý đăng bài", "", "## Tiêu đề"] + [f"- {t}" for t in kit["titles"]]
    if kit.get("llmTitles"):
        md += ["", "_Gợi ý thêm từ LLM (kiểm tra kỹ):_"] + [f"- {t}" for t in kit["llmTitles"]]
    md += ["", "## Mô tả", "", kit["description"], "", "## Hashtag", "", " ".join(kit["hashtags"]), "", f"_{kit['note']}_"]
    p = out_dir / "publish.md"
    p.write_text("\n".join(md) + "\n", encoding="utf-8")
    return p
