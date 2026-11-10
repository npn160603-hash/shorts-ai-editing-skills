# Skill 04 — Smart Cut & Pacing

```bash
ffmpeg -hide_banner -i input.mp4 -af silencedetect=noise=-35dB:d=0.25 -f null - 2> silence.log
python -c "import sys,json; sys.path[:0]=['lib','../../core/lib']; import pacing; \
tr=json.load(open('transcript.json',encoding='utf-8')); \
print(json.dumps(pacing.plan_cuts(tr, 17.0, 30, 'normal', 0.35, open('silence.log').read()), ensure_ascii=False, indent=2))"
python tests/test_pacing.py
```
Ví dụ: `examples/cut-list.example.json` (từ `examples/silencedetect.log.txt` + transcript mẫu trong `core/examples`).
