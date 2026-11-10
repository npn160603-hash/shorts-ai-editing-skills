# Skill 03 — Cinematic Camera Movement

```bash
python tests/test_camera.py
ffmpeg -i cut.mp4 -vf "$(cat examples/camera.ffmpeg-filter.txt)" -c:a copy out/rev-1/camera.mp4
```
(PowerShell: `-vf (Get-Content examples/camera.ffmpeg-filter.txt -Raw).Trim()`)
