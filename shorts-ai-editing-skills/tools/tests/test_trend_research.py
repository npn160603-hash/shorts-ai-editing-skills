import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import trend_research as T  # noqa: E402

NOW = dt.datetime(2026, 11, 10, tzinfo=dt.timezone.utc)
ITEMS = [
    {"id": "a1", "snippet": {"title": "3 mẹo tiết kiệm 2 giờ mỗi ngày?", "channelTitle": "Kênh A", "publishedAt": "2026-11-08T00:00:00Z"},
     "statistics": {"viewCount": "200000", "likeCount": "9000", "commentCount": "300"}, "contentDetails": {"duration": "PT45S"}},
    {"id": "b2", "snippet": {"title": "Cách dậy sớm KHÔNG mệt", "channelTitle": "Kênh B", "publishedAt": "2026-11-03T00:00:00Z"},
     "statistics": {"viewCount": "350000"}, "contentDetails": {"duration": "PT1M2S"}},
    {"id": "c3", "snippet": {"title": "Long video", "channelTitle": "Kênh C", "publishedAt": "2026-11-09T00:00:00Z"},
     "statistics": {"viewCount": "999999"}, "contentDetails": {"duration": "PT12M"}},
]


class TestTrend(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(T.iso_duration("PT1M2S"), 62)
        self.assertEqual(T.iso_duration("PT45S"), 45)

    def test_rank_by_views_per_day_and_filter_long(self):
        rows = T.normalize(ITEMS, 180, now=NOW)
        self.assertEqual([r["id"] for r in rows], ["a1", "b2"])  # 100k/day beats 50k/day; 12-min video dropped
        self.assertEqual(rows[0]["url"], "https://www.youtube.com/shorts/a1")

    def test_patterns_and_report(self):
        rows = T.normalize(ITEMS, 180, now=NOW)
        pat = T.patterns(rows)
        self.assertEqual(pat["titleHooks"]["number"], "1/2")
        self.assertEqual(pat["titleHooks"]["question"], "1/2")
        d = Path(tempfile.mkdtemp())
        links = d / "l.txt"
        links.write_text("https://www.douyin.com/video/123 | hook hay\n", encoding="utf-8")
        p = T.write_report(d / "r", "test", rows, pat, T.read_extra(str(links)))
        md = p.read_text(encoding="utf-8")
        self.assertIn("douyin.com/video/123 — hook hay", md)
        self.assertIn("| 1 | 3 mẹo", md)

    def test_search_uses_official_api_params(self):
        seen = []
        T.search_ids("K", "mẹo", "VN", "vi", 7, 50, http=lambda u: seen.append(u) or {"items": [{"id": {"videoId": "x"}}]})
        self.assertIn("googleapis.com/youtube/v3/search", seen[0])
        self.assertIn("videoDuration=short", seen[0])
        self.assertIn("order=viewCount", seen[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
