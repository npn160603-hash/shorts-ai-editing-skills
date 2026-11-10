# PROMPT CHO CODEX — TÍCH HỢP SHORTS AI EDITING SKILLS VÀO EDITOR

> Mở Codex ở **thư mục gốc của tool edit Shorts chạy localhost**. Gói này nằm ở `PATH_TO/shorts-ai-editing-skills` (cạnh `shorts-motion-designer` V1.1). Thay `PATH_TO` bằng đường dẫn thật.

Bạn là Senior Video Editing Systems Engineer. Nhiệm vụ: tích hợp các Skill trong gói vào editor **theo giai đoạn**, không viết lại editor, không làm mất tính năng cũ.

## Đọc trước khi sửa code
`00-ASSESSMENT.md`, `core/references/contracts.md`, `orchestrator/SKILL.md`, `orchestrator/integration-guide.md`, rồi `SKILL.md` + `integration-guide.md` của Skill thuộc giai đoạn đang làm. Chạy `python PATH_TO/shorts-ai-editing-skills/scripts/check_all.py` để chắc gói nguyên vẹn.

## P0 — Audit (chỉ đọc) → Capability Manifest
0. Chạy `python PATH_TO/shorts-ai-editing-skills/scripts/doctor.py` trên máy người dùng; mọi dòng FAIL phải xử lý trước (thường là FFmpeg thiếu libass/xfade).
1. Xác định stack render thật (FFmpeg/Remotion/Python/Canvas), nơi trim/concat, nơi burn phụ đề, nơi export, job queue, ASR có word timestamps không.
2. Git status, baseline test/build; bảo vệ file chưa commit và cài đặt người dùng.
3. Viết `config/capability-manifest.json` theo `core/schemas/capability-manifest.schema.json`: mỗi key có `status` + `evidence` (file/hàm). `implemented` chỉ khi **export** dùng được.
4. Chạy `orchestrator/lib/orchestrate.py` với lệnh mẫu + manifest thật; lưu plan; báo cáo các Skill `blocked` (`needsIntegration`).

## P1 — Không cần AI: Cut (04) → Captions (02) → Audio loudness (07) → QA (08)
- Cách nhanh nhất để thử: `scripts/shorts.py edit <clip> --transcript <file>` (CLI một lệnh, ghi `progress.jsonl`). Backend web có thể gọi CLI này như một job (`--detach` + `status`), hoặc import `runner.py` trực tiếp.
- Thêm module mới (vd. `server/ai_edit/`) dùng `orchestrator/lib/runner.py`. Nếu editor dùng FFmpeg thuần: dùng `FfmpegBackend`; nếu có pipeline riêng: viết backend 5 hàm theo `orchestrator/integration-guide.md` (Bước 1b). Không đổi API cũ.
- Transcript: đưa output ASR sẵn có qua `core/lib/sae_asr.py` (`load_any`); tôn trọng `wordTimestampsReliable` + `reliabilityNotes`.
- Video VFR: Runner tự chuẩn hoá ra file mới trong `rev-<n>/`; không sửa file gốc.
- Mỗi lần chạy: thư mục `projects/<id>/ai-edit/rev-<n>/` chứa JSON từng stage, preview, QA report, contact sheet.
- Feature flag `aiEditEnabled` + registry từng Skill. OFF ⇒ output giống baseline (so ffprobe + hash audio).
- Render BEFORE (flag OFF) và AFTER (flag ON) từ **cùng clip** 12–20 s 9:16 (dùng clip thật của người dùng nếu được phép, không upload đi đâu).
- Nghiệm thu P1: A/V lệch ≤ 1 frame; −14 ± 1 LUFS, TP ≤ −1 dBTP; không click ở điểm cắt; caption không bịa chữ, không tách từ ghép/số+đơn vị, không vượt safe area; QA gate pass; xem contact sheet bằng mắt.

## P2 → P4
Làm theo `00-ASSESSMENT.md` §7: Director + Camera → Transitions + subject boxes → VFX/nhạc/SFX/LLM (opt-in). Mỗi giai đoạn: test gói pass, render AFTER thật, QA pass, báo cáo.

## Ràng buộc
- Không xoá/reset/clean/stash; không ghi đè video hay file người dùng; không push.
- Không thêm dependency nặng/model khi chưa được người dùng đồng ý; không API trả phí; không upload media.
- Không nhận chuỗi filter FFmpeg tự do từ JSON/LLM — chỉ dùng hàm builder trong `lib/`.
- Nhạc/SFX chỉ từ file có license khai báo.
- Không tuyên bố hoàn thành khi chưa render bằng pipeline của editor và xem kết quả.

## Báo cáo mỗi giai đoạn
(1) stack thật + manifest; (2) file thêm/sửa; (3) Skill nào chạy, chế độ nào, vì sao; (4) đường dẫn BEFORE/AFTER + JSON + contact sheet; (5) kết quả test/ffprobe/loudness/QA; (6) hiệu năng (giây render / giây video); (7) cách tắt & rollback; (8) giới hạn còn lại.
