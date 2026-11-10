# Skill 08 — AI Visual Quality Reviewer
```bash
python tests/test_review.py
ffmpeg -hide_banner -i final.mp4 -vf "fps=2,scale=270:-2,tile=6x6" -frames:v 1 contact_sheet.png
```
Quy tắc: `references/review-rubric.md`. Ví dụ: `examples/qa-report.example.json`.
