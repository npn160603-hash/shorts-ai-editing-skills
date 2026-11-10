"""Trend research for Shorts — what is blowing up and how it is packaged (metadata only, no downloads).

Uses the official YouTube Data API v3 (free key: Google Cloud Console -> enable "YouTube Data API v3"
-> Credentials -> API key). Default quota is 10,000 units/day; one `search` costs ~100 units + 1 per
50 videos of details, so ~90 searches/day.

    set YOUTUBE_API_KEY=...
    python tools/trend_research.py search --query "mẹo tiết kiệm" --region VN --lang vi --days 7 --max 50
    python tools/trend_research.py trending --region VN                       # most-popular chart, Shorts only
    python tools/trend_research.py search --query "..." --extra-links douyin_links.txt   # add links you found by hand

Output: <out>/<date>-<slug>/report.md (ranked table + patterns), report.csv, report.json.
Ranking uses views/day since upload (fairer than raw views). Patterns: duration spread, title
hooks (numbers, questions, "how/why", emoji, ALL CAPS), frequent title words, top channels.
Douyin/TikTok have no public search API: put links you collect manually (one per line, optional
" | note") in a text file and pass --extra-links; they are listed in the report for side-by-side study.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

API = "https://www.googleapis.com/youtube/v3"
STOP = set("và là của cho với những các một nhiều thì mà để khi này đó thế nào bạn tôi mình có không được trong ra vào lên "
           "the a an and or but to of in on is are be it this that you i we for with how why what".split())


def _get(url: str) -> Dict:
    req = urllib.request.Request(url, headers={"User-Agent": "shorts-ai-editing-skills/1.2 trend research"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def iso_duration(s: str) -> float:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0.0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50] or "trending"


def details(key: str, ids: List[str], http=_get) -> List[Dict]:
    out = []
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i + 50]), "key": key})
        out += http(f"{API}/videos?{q}").get("items", [])
    return out


def search_ids(key: str, query: str, region: str, lang: str, days: int, n: int, http=_get) -> List[str]:
    after = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = {"part": "snippet", "q": query, "type": "video", "order": "viewCount", "publishedAfter": after,
         "videoDuration": "short", "maxResults": min(50, n), "key": key}
    if region:
        p["regionCode"] = region
    if lang:
        p["relevanceLanguage"] = lang
    data = http(f"{API}/search?{urllib.parse.urlencode(p)}")
    return [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]


def trending_items(key: str, region: str, category: Optional[str], http=_get) -> List[Dict]:
    p = {"part": "snippet,statistics,contentDetails", "chart": "mostPopular", "regionCode": region or "VN", "maxResults": 50, "key": key}
    if category:
        p["videoCategoryId"] = category
    return http(f"{API}/videos?{urllib.parse.urlencode(p)}").get("items", [])


def normalize(items: List[Dict], max_dur: float, now: Optional[dt.datetime] = None) -> List[Dict]:
    now = now or dt.datetime.now(dt.timezone.utc)
    rows = []
    for it in items:
        sn, st, cd = it.get("snippet", {}), it.get("statistics", {}), it.get("contentDetails", {})
        dur = iso_duration(cd.get("duration", ""))
        if not dur or dur > max_dur:
            continue
        pub = dt.datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        age_days = max((now - pub).total_seconds() / 86400, 0.25)
        views = int(st.get("viewCount", 0) or 0)
        likes, comments = int(st.get("likeCount", 0) or 0), int(st.get("commentCount", 0) or 0)
        rows.append({"id": it["id"], "title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                     "publishedAt": sn["publishedAt"], "ageDays": round(age_days, 1), "durationSec": dur, "views": views,
                     "viewsPerDay": round(views / age_days), "likes": likes, "comments": comments,
                     "engagement": round((likes + comments) / views, 4) if views else 0.0,
                     "tags": sn.get("tags", [])[:10], "url": f"https://www.youtube.com/shorts/{it['id']}"})
    rows.sort(key=lambda r: -r["viewsPerDay"])
    return rows


def patterns(rows: List[Dict]) -> Dict:
    if not rows:
        return {}
    titles = [r["title"] for r in rows]
    words = Counter(w for t in titles for w in re.findall(r"[^\W\d_]{3,}", t.lower()) if w not in STOP)
    hook = {
        "number": sum(bool(re.search(r"\d", t)) for t in titles),
        "question": sum("?" in t for t in titles),
        "how/why/cách/tại sao": sum(bool(re.search(r"\b(how|why|cách|tại sao|vì sao|bí quyết)\b", t.lower())) for t in titles),
        "emoji": sum(any(ord(c) > 0x2600 for c in t) for t in titles),
        "ALL CAPS word": sum(bool(re.search(r"\b[A-ZĐÂĂÊÔƠƯ]{4,}\b", t)) for t in titles),
        "#shorts tag": sum("#short" in t.lower() for t in titles),
    }
    durs = [r["durationSec"] for r in rows]
    return {"count": len(rows), "durationSec": {"median": statistics.median(durs), "min": min(durs), "max": max(durs)},
            "medianViewsPerDay": statistics.median(r["viewsPerDay"] for r in rows),
            "medianEngagement": statistics.median(r["engagement"] for r in rows),
            "titleHooks": {k: f"{v}/{len(rows)}" for k, v in hook.items()},
            "topTitleWords": words.most_common(15),
            "topChannels": Counter(r["channel"] for r in rows).most_common(8)}


def read_extra(path: Optional[str]) -> List[Dict]:
    if not path:
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            link, _, note = line.partition("|")
            out.append({"url": link.strip(), "note": note.strip()})
    return out


def write_report(out_dir: Path, title: str, rows: List[Dict], pat: Dict, extra: List[Dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps({"title": title, "patterns": pat, "videos": rows, "manualLinks": extra},
                                                    ensure_ascii=False, indent=2), encoding="utf-8")
    with (out_dir / "report.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["title", "channel", "views", "viewsPerDay", "engagement", "durationSec", "publishedAt", "url"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    md = [f"# {title}", "", f"_Tạo lúc {dt.datetime.now():%Y-%m-%d %H:%M} — chỉ metadata công khai, không tải video._", ""]
    if pat:
        md += ["## Mẫu hình", f"- Số video: {pat['count']} · thời lượng trung vị {pat['durationSec']['median']:.0f}s "
               f"(từ {pat['durationSec']['min']:.0f} đến {pat['durationSec']['max']:.0f}s)",
               f"- Lượt xem/ngày trung vị: {pat['medianViewsPerDay']:,} · tương tác trung vị: {pat['medianEngagement']:.2%}",
               "- Kiểu tiêu đề: " + ", ".join(f"{k} {v}" for k, v in pat["titleHooks"].items()),
               "- Từ hay gặp: " + ", ".join(f"{w} ({c})" for w, c in pat["topTitleWords"]),
               "- Kênh xuất hiện nhiều: " + ", ".join(f"{c} ({n})" for c, n in pat["topChannels"]), ""]
    md += ["## Xếp hạng theo lượt xem/ngày", "", "| # | Tiêu đề | Kênh | Xem/ngày | Tổng xem | Thời lượng | Link |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        t = r["title"].replace("|", "/")
        md.append(f"| {i} | {t} | {r['channel']} | {r['viewsPerDay']:,} | {r['views']:,} | {r['durationSec']:.0f}s | [xem]({r['url']}) |")
    if extra:
        md += ["", "## Link tự thu thập (Douyin/TikTok…)", ""]
        md += [f"- {e['url']}" + (f" — {e['note']}" if e["note"] else "") for e in extra]
    md += ["", "## Ghi chú khi xem (điền tay)", "", "| # | Hook 2s đầu | Nhịp cắt | Kiểu phụ đề | Camera/hiệu ứng | CTA |", "|---|---|---|---|---|---|"]
    md += [f"| {i} |  |  |  |  |  |" for i in range(1, min(len(rows), 10) + 1)]
    p = out_dir / "report.md"
    p.write_text("\n".join(md) + "\n", encoding="utf-8")
    return p


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--query", required=True)
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--max", type=int, default=50)
    s.add_argument("--lang", default="vi")
    t = sub.add_parser("trending")
    t.add_argument("--category", help="YouTube category id, e.g. 22 People&Blogs, 24 Entertainment, 26 Howto")
    for p in (s, t):
        p.add_argument("--region", default="VN")
        p.add_argument("--max-duration", type=float, default=180)
        p.add_argument("--extra-links")
        p.add_argument("--out", default="research")
    a = ap.parse_args()
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key:
        print("set YOUTUBE_API_KEY (free: Google Cloud Console -> YouTube Data API v3 -> API key)")
        return 2
    try:
        if a.cmd == "search":
            items = details(key, search_ids(key, a.query, a.region, a.lang, a.days, a.max))
            title = f"Shorts nổi bật: \"{a.query}\" · {a.region} · {a.days} ngày"
            name = slug(a.query)
        else:
            items = trending_items(key, a.region, a.category)
            title = f"Thịnh hành {a.region}" + (f" · category {a.category}" if a.category else "")
            name = f"trending-{a.region.lower()}"
    except Exception as e:  # noqa: BLE001
        print(f"YouTube API error: {e}")
        return 1
    rows = normalize(items, a.max_duration)
    out = Path(a.out) / f"{dt.date.today():%Y%m%d}-{name}"
    p = write_report(out, title, rows, patterns(rows), read_extra(a.extra_links))
    print(f"{len(rows)} Shorts · report -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
