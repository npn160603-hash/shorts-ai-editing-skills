# Tích hợp Orchestrator vào editor Shorts localhost

## Bước 0 — Audit tạo Capability Manifest (bắt buộc)
1. Đọc source editor thật. Với mỗi key trong `../core/schemas/capability-manifest.schema.json`, ghi `status` + `evidence` (file/hàm/test).
2. `implemented` chỉ khi **render export** dùng được (không chỉ preview). Preview HTML ≠ export.
3. Lưu `config/capability-manifest.json` trong repo editor. Validate:
   `python core/lib/sae_schema.py config/capability-manifest.json core/schemas/capability-manifest.schema.json`

## Bước 1 — Nối vào backend (không viết lại editor)
- Thêm endpoint/job type mới, ví dụ `POST /api/ai-edit/plan` (chỉ lập plan, không render) và `POST /api/ai-edit/run`.
- Job `run` gọi các stage theo `stages[]`. Mỗi stage là adapter mỏng gọi code **đã có** của editor (trim, drawtext, export…) hoặc lib tham chiếu trong Skill.
- Lưu mọi artefact vào `projects/<id>/ai-edit/rev-<n>/` (plan JSON, preview, QA report). Không ghi vào file nguồn.

## Bước 1b — Backend của editor (thay `FfmpegBackend`)
`Runner` chỉ gọi backend qua 5 hàm. Nếu editor đã có pipeline render, viết lớp mới cùng chữ ký:

| Hàm | Trả về | Gợi ý |
|---|---|---|
| `silence_log(src)` | stderr kiểu `silencedetect` | gọi FFmpeg của editor |
| `render(src, sections, out_dir, final, has_audio, assets)` | đường dẫn mp4 mới trong `out_dir` | map `cutList`/`transitionPlan`/`cameraTrack`/`vfxPlan`/`captionTrack`/`audioMixPlan` sang API render của editor |
| `measure_loudness(path, targets)` | dict `input_i/input_tp/...` | `audio_mix.measure_cmd` |
| `inspect(path)` | `{probe, logs}` | `review.detect_cmds` |
| `contact_sheet(path, png)` | — | `review.contact_sheet_cmd` |

Nếu editor dùng FFmpeg thuần, có thể dùng thẳng `FfmpegBackend` (đã kiểm với FFmpeg 6.1).

## Bước 2 — Bật/tắt & rollback
- `skills.registry.json` → `enabled`. UI: một toggle mỗi Skill + chọn intensity.
- Feature flag tổng `aiEditEnabled=false` ⇒ đường code cũ chạy y nguyên (test hồi quy: so ffprobe + hash audio với baseline).
- Rollback = chọn revision cũ (`rev-<n>`), không xoá gì. Gỡ hẳn = tắt flag + xoá route mới.

## Bước 3 — Tiến độ & huỷ
- Mỗi stage cập nhật `progress` + log; hỗ trợ cancel; dọn file tạm (PNG sequence, wav tạm) khi xong/huỷ.

## Nghiệm thu
- [ ] Manifest có evidence cho từng `implemented`.
- [ ] Lệnh mẫu → plan khớp `examples/orchestration-plan.example.json` (với manifest tương đương).
- [ ] Render preview + export ở revision mới; file cũ không đổi (so mtime/hash).
- [ ] Flag OFF = baseline.
