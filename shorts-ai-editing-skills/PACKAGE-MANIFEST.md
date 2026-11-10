# Package manifest

- Name: `shorts-ai-editing-skills` v1.2.0 (2026-11-10) — xem `CHANGELOG.md`. Ngôn ngữ tài liệu: tiếng Việt; tên kỹ thuật/khóa JSON: tiếng Anh.
- Phụ thuộc: Python ≥ 3.9 (stdlib), FFmpeg ≥ 6.0 (+libass cho phụ đề ASS). `jsonschema` tuỳ chọn (chỉ để đối chiếu test).
- Tái sử dụng (không sửa): `../shorts-motion-designer` V1.1 — schema `ShortsMotionPlan`, preset overlay, timeline contract.
- Gồm: core (4 schema, 4 lib), orchestrator, 8 Skill (mỗi Skill: SKILL.md 12 mục, README, integration-guide, references, schemas, examples, lib, tests), scripts/check_all.py, scripts/run_pipeline_demo.py, install.ps1.
- Không gồm: renderer biên dịch sẵn, model AI, media người dùng, nhạc/SFX bản quyền (SFX ví dụ được tổng hợp bằng FFmpeg trong demo).
- Font kèm: Be Vietnam Pro (SIL OFL 1.1, `core/fonts/OFL.txt`). Phụ thuộc tuỳ chọn: `opencv-python-headless` 4.x (phát hiện mặt), `faster-whisper` (nhận dạng giọng nói local — chưa chạy thật trên máy thử vì không tải được model; phần chuyển đổi kết quả đã có test).
- Đã kiểm (máy thử Linux, Python 3.13, FFmpeg 6.1.1, OpenCV 4.14 cho test mặt): 102 unit/smoke test pass; Runner render 1080×1920@30, −14.0 LUFS, QA pass, vòng tự sửa hoạt động. Chưa kiểm trên Windows/editor của người dùng — chạy `scripts/doctor.py`.
- Cài (tuỳ chọn, không ghi đè): `install.ps1 -ProjectPath <repo editor>`.
