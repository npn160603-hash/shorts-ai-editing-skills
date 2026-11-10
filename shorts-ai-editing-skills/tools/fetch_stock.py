"""Download stock video clips from Pexels and Pixabay (official APIs, free keys) — stdlib only.

    set PEXELS_API_KEY=...      (https://www.pexels.com/api/)
    set PIXABAY_API_KEY=...     (https://pixabay.com/api/docs/)
    python tools/fetch_stock.py --query "buổi sáng cà phê" --query "laptop work desk" --per-source 5 --out D:\\sources

Saves to <out>/<query-slug>/<source>_<id>.mp4 and appends one record per clip to
<out>/credits.json + credits.csv (source, id, author, page URL, licence, query, file).
Existing files are never overwritten (skipped). Portrait clips are preferred; landscape clips
are still useful (Skill 03 reframes 16:9 -> 9:16) but rank lower.
Check each site's current licence terms before publishing; credits are kept so you can.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

UA = "shorts-ai-editing-skills/1.2 (+local stock fetcher)"
LICENSES = {"pexels": "Pexels License (https://www.pexels.com/license/)",
            "pixabay": "Pixabay Content License (https://pixabay.com/service/license-summary/)"}


def slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "query"


def _get_json(url: str, headers: Optional[Dict] = None) -> Dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _score(w: int, h: int, dur: float, want_portrait: bool, min_d: float, max_d: float) -> float:
    s = 0.0
    if want_portrait:
        s += 3.0 if h > w else 0.0
    s += min(h, 1920) / 1920 + min(w, 1080) / 1080
    if dur and (dur < min_d or dur > max_d):
        s -= 5.0
    return s


def search_pexels(key: str, query: str, n: int, portrait: bool, min_d: float, max_d: float, http=_get_json) -> List[Dict]:
    q = urllib.parse.urlencode({"query": query, "per_page": min(80, max(n * 3, 15)), **({"orientation": "portrait"} if portrait else {})})
    data = http(f"https://api.pexels.com/videos/search?{q}", {"Authorization": key})
    out = []
    for v in data.get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("link") and f.get("width") and f.get("height")]
        if not files:
            continue
        # best file not larger than 1080x1920-ish (avoid 4K downloads)
        files.sort(key=lambda f: (min(f["height"], f["width"]) <= 1080, f["height"] * f["width"]), reverse=True)
        f = files[0]
        out.append({"source": "pexels", "id": str(v["id"]), "url": f["link"], "width": f["width"], "height": f["height"],
                    "durationSec": float(v.get("duration") or 0), "author": (v.get("user") or {}).get("name", ""),
                    "pageUrl": v.get("url", ""), "license": LICENSES["pexels"], "query": query,
                    "score": _score(f["width"], f["height"], float(v.get("duration") or 0), portrait, min_d, max_d)})
    out.sort(key=lambda c: -c["score"])
    return out[:n]


def search_pixabay(key: str, query: str, n: int, portrait: bool, min_d: float, max_d: float, http=_get_json) -> List[Dict]:
    q = urllib.parse.urlencode({"key": key, "q": query, "per_page": min(200, max(n * 3, 15)), "safesearch": "true"})
    data = http(f"https://pixabay.com/api/videos/?{q}")
    out = []
    for h in data.get("hits", []):
        vids = h.get("videos", {})
        cand = [vids[k] for k in ("large", "medium", "small") if vids.get(k, {}).get("url")]
        if not cand:
            continue
        cand.sort(key=lambda f: (min(f["height"], f["width"]) <= 1080, f["height"] * f["width"]), reverse=True)
        f = cand[0]
        out.append({"source": "pixabay", "id": str(h["id"]), "url": f["url"], "width": f["width"], "height": f["height"],
                    "durationSec": float(h.get("duration") or 0), "author": h.get("user", ""), "pageUrl": h.get("pageURL", ""),
                    "license": LICENSES["pixabay"], "query": query,
                    "score": _score(f["width"], f["height"], float(h.get("duration") or 0), portrait, min_d, max_d)})
    out.sort(key=lambda c: -c["score"])
    return out[:n]


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return False
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    tmp.rename(dest)
    return True


def append_credits(out: Path, rows: List[Dict]) -> None:
    jf = out / "credits.json"
    old = json.loads(jf.read_text(encoding="utf-8")) if jf.is_file() else []
    seen = {(r["source"], r["id"]) for r in old}
    new = [r for r in rows if (r["source"], r["id"]) not in seen]
    jf.write_text(json.dumps(old + new, ensure_ascii=False, indent=2), encoding="utf-8")
    cf = out / "credits.csv"
    write_header = not cf.is_file()
    with cf.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "id", "author", "pageUrl", "license", "query", "file", "durationSec", "width", "height"],
                           extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerows(new)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", action="append", required=True, help="repeat for several queries (English often finds more)")
    ap.add_argument("--per-source", type=int, default=5)
    ap.add_argument("--sources", default="pexels,pixabay")
    ap.add_argument("--landscape-ok", action="store_true", help="do not prefer portrait")
    ap.add_argument("--min-duration", type=float, default=3.0)
    ap.add_argument("--max-duration", type=float, default=60.0)
    ap.add_argument("--out", default="sources")
    ap.add_argument("--dry-run", action="store_true", help="list candidates only")
    a = ap.parse_args()
    keys = {"pexels": os.environ.get("PEXELS_API_KEY", ""), "pixabay": os.environ.get("PIXABAY_API_KEY", "")}
    srcs = [s for s in a.sources.split(",") if s]
    usable = [s for s in srcs if keys.get(s)]
    for s in srcs:
        if not keys.get(s):
            print(f"skip {s}: set {s.upper()}_API_KEY (free key)")
    if not usable:
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for q in a.query:
        for s in usable:
            try:
                fn = search_pexels if s == "pexels" else search_pixabay
                cands = fn(keys[s], q, a.per_source, not a.landscape_ok, a.min_duration, a.max_duration)
            except Exception as e:  # noqa: BLE001
                print(f"[{s}] '{q}': search failed: {e}")
                continue
            print(f"[{s}] '{q}': {len(cands)} clips")
            for c in cands:
                dest = out / slug(q) / f"{s}_{c['id']}.mp4"
                dest.parent.mkdir(parents=True, exist_ok=True)
                c["file"] = str(dest)
                if a.dry_run:
                    print(f"   {c['width']}x{c['height']} {c['durationSec']:.0f}s  {c['pageUrl']}")
                    continue
                try:
                    got = download(c["url"], dest)
                    print(f"   {'saved' if got else 'exists'} {dest}")
                    rows.append(c)
                except Exception as e:  # noqa: BLE001
                    print(f"   failed {c['pageUrl']}: {e}")
                time.sleep(0.3)
    if rows:
        append_credits(out, rows)
        print(f"\n{len(rows)} clips · credits -> {out / 'credits.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
