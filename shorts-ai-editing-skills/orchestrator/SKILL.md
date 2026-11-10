---
name: ai-editing-orchestrator
description: >-
  Điều phối toàn bộ Skill dựng Shorts: đọc yêu cầu người dùng + Capability Manifest của editor,
  chọn Skill, chế độ chạy, thứ tự, ngân sách hiệu ứng, áp luật xung đột, render preview, QA,
  vòng sửa và export không ghi đè. Dùng khi người dùng ra lệnh dựng cả video ("edit video này
  theo phong cách Shorts...").
---

# AI Editing Orchestrator

> **Agent chạy nhanh:** `python <gói>/scripts/shorts.py edit "<video>" --instruction "<yêu cầu>"` — xem `<gói>/AGENTS.md`. Phần dưới mô tả chi tiết bên trong lệnh đó.

## 1. Mục đích
Biến một câu lệnh tự nhiên thành **OrchestrationPlan** tất định: Skill nào chạy, ở chế độ nào, theo thứ tự nào, trong ngân sách hiệu ứng nào — chỉ dùng năng lực editor **thật sự có** (`implemented`).

## 2. Khi nào dùng
- Lệnh dựng tổng thể nhiều bước (cắt + phụ đề + zoom + âm thanh…).
- Cần chạy lại sau khi QA báo lỗi (vòng revise).
- Cần biết vì sao một hiệu ứng **không** được áp (báo cáo `skills[].reasons`).

## 3. Khi nào không dùng
- Chỉ sửa một thứ nhỏ (đổi màu chữ caption) → gọi thẳng Skill sở hữu section đó.
- Editor chưa có `capability-manifest.json` đã audit → làm audit trước (xem `integration-guide.md`).

## 4. Đầu vào
- `EditRequest` — `schemas/edit-request.schema.json` (lệnh + `constraints` phạm vi cho phép).
- `CapabilityManifest` — `../core/schemas/capability-manifest.schema.json`.
- `skills.registry.json` — bật/tắt từng Skill (`enabled`).

## 5. Đầu ra
- `OrchestrationPlan` — `schemas/orchestration-plan.schema.json` (ví dụ: `examples/orchestration-plan.example.json`).
- Mỗi vòng chạy (`lib/runner.py`): `ai-edit/rev-<n>/` gồm `shorts-edit-plan.json` (envelope, hợp lệ `../core/schemas/shorts-edit-plan.schema.json`), JSON từng section, `run-params.json` (tham số + conflict log), `preview.mp4`, `qa-report.json`, `contact_sheet.png`; vòng cuối thêm `final.mp4` + `run-report.json`.

## 6. Quy trình
1. Validate 3 input. Sai schema → dừng, không đoán.
2. Diễn giải intent (`references/intent-mapping.md`); `intent` có cấu trúc ghi đè keyword.
3. Với từng Skill theo `stage`: `enabled`? được yêu cầu? `requires` đều `implemented`? → `planned | fallback | skipped | blocked` + `mode` + lý do.
4. Chọn `effectBudget` theo intensity (subtle/normal/dynamic).
5. Lập `stages` theo `references/pipeline-stages.md` (cut luôn trước; audio sau transition/caption).
6. `Runner.build_sections()` chạy từng Skill; mỗi Skill chỉ ghi section mình sở hữu (CR-08). Nguồn VFR được chuẩn hoá CFR trước (file mới).
7. `conflicts.resolve()` áp CR-01…CR-10 ở **một chỗ** và ghi log (`references/conflict-rules.md`).
8. Backend render preview → Skill 08 QA → `apply_fix()` đổi tham số của Skill sở hữu → revision mới. Dừng khi QA pass, hết `maxReviewIterations`, không còn fix tự động được, hoặc lỗi lặp lại y hệt (không tiến triển).
9. Export vào **revision mới**; ffprobe + đo loudness; `run-report.json` liệt kê `needsHuman`.

## 7. Công cụ / thư viện
Python ≥ 3.9 stdlib: `lib/orchestrate.py` (lập kế hoạch), `lib/runner.py` (thực thi + vòng sửa), `lib/conflicts.py` (CR-01…10). Render qua **backend**: `FfmpegBackend` tham chiếu, hoặc backend của editor (`silence_log`, `render`, `measure_loudness`, `inspect`, `contact_sheet`). LLM local **tùy chọn** chỉ để điền `intent`.

## 8. Thuật toán / preset
- Keyword parser VI/EN có bỏ dấu; intent tường minh ghi đè.
- Ngân sách: `BUDGETS` trong `lib/orchestrate.py` (accent/10s, khoảng cách tối thiểu, camera move/10s, số transition, SFX/10s).
- Trạng thái `blocked` = capability chỉ `documented` → danh sách việc tích hợp cho Codex (`needsIntegration`).

## 9. Phối hợp Skill
Thứ tự và quyền sở hữu nằm trong `skills.registry.json`. Overlay cuối cùng biên dịch qua **Shorts Motion Designer V1.1** (`motionPlan`) — không tạo engine overlay mới.

## 10. Kiểm tra & nghiệm thu
- `python tests/test_orchestrator.py` và `python tests/test_runner.py` pass (test runner render thật: vòng 1 lỗi tốc độ đọc → tự đổi preset → vòng 2 pass; chạy lại không ghi đè revision cũ).
- Lệnh mẫu trong đề bài → plan: cut + director + captions + camera + transitions(restrained) + audio(speech-first) + QA; VFX **không** bật.
- Đổi manifest `transcript.wordTimestamps` → `missing` ⇒ captions chuyển `phrase` + `fallback`.
- Tắt mọi Skill trong registry ⇒ chỉ còn stage hạ tầng; render = baseline (test hồi quy trên editor thật).

## 11. Giới hạn
- Không tự hiểu ngữ nghĩa sâu; câu lệnh mơ hồ dùng mặc định `professional/normal` và ghi rõ trong plan.
- Không đo được chất lượng thẩm mỹ; việc đó do QA + người xem.

## 12. Fallback
- Thiếu manifest → chỉ chạy chế độ "plan-only" (không render), báo cáo việc cần audit.
- Skill lỗi khi chạy → section `failed`, pipeline tiếp tục như Skill bị tắt; không làm hỏng audio/timeline gốc.
- Conflict-check báo `error` (sai owner, thiếu seed, đường dẫn ghi đè) → dừng trước khi render, ghi `needsHuman`.
- QA vẫn còn lỗi sau vòng cuối → export nhưng **liệt kê lỗi**; hoặc chờ duyệt nếu `requireApprovalBeforeExport`.
