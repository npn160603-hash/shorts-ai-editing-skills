import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import fetch_stock as F  # noqa: E402

PEX = {"videos": [
    {"id": 1, "duration": 12, "url": "https://www.pexels.com/video/1/", "user": {"name": "A"},
     "video_files": [{"file_type": "video/mp4", "link": "https://x/1_4k.mp4", "width": 2160, "height": 3840},
                     {"file_type": "video/mp4", "link": "https://x/1_hd.mp4", "width": 1080, "height": 1920}]},
    {"id": 2, "duration": 9, "url": "https://www.pexels.com/video/2/", "user": {"name": "B"},
     "video_files": [{"file_type": "video/mp4", "link": "https://x/2.mp4", "width": 1920, "height": 1080}]}]}
PIX = {"hits": [{"id": 7, "duration": 20, "pageURL": "https://pixabay.com/videos/7/", "user": "C",
                 "videos": {"large": {"url": "https://y/7l.mp4", "width": 1920, "height": 1080},
                            "medium": {"url": "https://y/7m.mp4", "width": 1280, "height": 720}}}]}


class TestFetch(unittest.TestCase):
    def test_pexels_prefers_portrait_and_avoids_4k(self):
        c = F.search_pexels("k", "coffee", 2, True, 3, 60, http=lambda url, h=None: PEX)
        self.assertEqual(c[0]["id"], "1")
        self.assertEqual(c[0]["url"], "https://x/1_hd.mp4")
        self.assertIn("Pexels License", c[0]["license"])

    def test_pixabay(self):
        c = F.search_pixabay("k", "city", 1, True, 3, 60, http=lambda url, h=None: PIX)
        self.assertEqual((c[0]["width"], c[0]["author"]), (1920, "C"))

    def test_slug_and_credits(self):
        self.assertEqual(F.slug("Buổi sáng cà phê!"), "buoi-sang-ca-phe")
        import tempfile
        d = Path(tempfile.mkdtemp())
        row = {"source": "pexels", "id": "1", "author": "A", "pageUrl": "u", "license": "L", "query": "q", "file": "f"}
        F.append_credits(d, [row])
        F.append_credits(d, [row])  # no duplicate
        import json
        self.assertEqual(len(json.loads((d / "credits.json").read_text(encoding="utf-8"))), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
