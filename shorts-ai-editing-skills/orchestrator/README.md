# AI Editing Orchestrator

Bộ não điều phối của gói `shorts-ai-editing-skills`. Đọc lệnh người dùng, năng lực thực của editor và registry Skill → xuất kế hoạch chạy có lý do.

```bash
python lib/orchestrate.py examples/edit-request.example.json \
  ../core/examples/capability-manifest.example.json ../skills.registry.json
python tests/test_orchestrator.py
python tests/test_runner.py        # vòng revise thật với FFmpeg
```
Chạy cả chuỗi trong code:
```python
import runner as RN
rep = RN.Runner(request, manifest, registry, project_dir, assets={...}, sfx_library=lib).run("input.mp4", "transcript.json")
print(rep["final"], rep["needsHuman"])
```

Đọc: `SKILL.md` → `references/pipeline-stages.md` → `references/conflict-rules.md` → `integration-guide.md`.
