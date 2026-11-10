# Skill 07 — Audio Editing Director
```bash
python tests/test_audio.py
# Đo loudness
ffmpeg -hide_banner -nostats -i cut.mp4 -vn -af loudnorm=I=-14:TP=-1:LRA=9:print_format=json -f null -
```
Ví dụ: `examples/audio-mix-plan.example.json`, `examples/sfx-library.example.json` (SFX tự tổng hợp, license `own`).
