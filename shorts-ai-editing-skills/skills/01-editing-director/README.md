# Skill 01 — AI Video Editing Director

```bash
python -c "import sys,json; sys.path[:0]=['lib']; import director as d; \
tr=json.load(open('../04-smart-cut-pacing/examples/transcript.output-time.example.json',encoding='utf-8')); \
a=d.analyze(tr,14.1); print(json.dumps(d.decide(a,'normal',[2.0333,8.0667],tr['words']),ensure_ascii=False,indent=2))"
python tests/test_director.py
```
Bảng quyết định: `references/decision-rules.md`.
