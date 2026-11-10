# Skill 02 — Smart Dynamic Captions

```bash
python tests/test_captions.py
# burn thử ASS mẫu (fontsdir chứa Be Vietnam Pro hoặc font có tiếng Việt):
ffmpeg -i cut.mp4 -vf "subtitles=examples/captions.example.ass:fontsdir=C\\:/Windows/Fonts" -c:a copy out/rev-1/captions.mp4
```
Ví dụ: `examples/caption-track.example.json`, `examples/captions.example.ass`, `examples/motion-plan.compiled.example.json` (hợp lệ schema Shorts Motion Designer V1.1).
