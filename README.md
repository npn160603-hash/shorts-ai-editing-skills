# Shorts AI Editing — skill packs

Bộ Skill giúp AI tự dựng YouTube Shorts / TikTok / Reels (local, Python + FFmpeg).

| Thư mục | Nội dung |
|---|---|
| `shorts-ai-editing-skills/` | v1.3 — 8 Skill + Orchestrator + Runner + CLI `scripts/shorts.py` (`edit`, `clips`, `story`, `batch`) + lớp đồ hoạ + bộ đăng bài + tích hợp OpenCode. Bắt đầu tại `shorts-ai-editing-skills/README.md`. |
| `shorts-motion-designer/` | Shorts Motion Designer Standalone V1.1 (gói gốc, giữ nguyên) — schema `ShortsMotionPlan` được tái sử dụng. |

```bash
python shorts-ai-editing-skills/scripts/doctor.py
python shorts-ai-editing-skills/scripts/check_all.py
python shorts-ai-editing-skills/scripts/shorts.py edit video.mp4 --transcript video.srt
python shorts-ai-editing-skills/scripts/shorts.py clips podcast.mp4 --transcript podcast.srt --count 5
python shorts-ai-editing-skills/scripts/shorts.py story kichban.txt --tts sapi --library D:/stock
```
Font kèm theo: Be Vietnam Pro (SIL OFL 1.1, `shorts-ai-editing-skills/core/fonts/OFL.txt`).
