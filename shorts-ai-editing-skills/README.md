# Shorts AI Editing Skills — v1.0 (mở rộng cho Shorts Motion Designer V1.1)

Gói **8 Skill + 1 Orchestrator + hợp đồng chung** giúp AI dựng YouTube Shorts / TikTok / Reels như một editor: hiểu nội dung, cắt nhịp, phụ đề động, camera, chuyển cảnh, VFX, âm thanh, tự kiểm tra rồi sửa.

- Chạy local, **chỉ Python stdlib + FFmpeg** (đã có trong hầu hết editor). Không cloud, không API trả phí, không model bắt buộc.
- Mỗi Skill có `SKILL.md` (12 mục), `README.md`, `integration-guide.md`, `schemas/`, `examples/`, `lib/` (runtime tham chiếu), `tests/`.
- Có **Runner** chạy cả chuỗi: lập kế hoạch → dựng → kiểm xung đột → render preview → QA → tự sửa → xuất bản mới, không ghi đè.
- Đã chạy thật: 102 test (gồm render FFmpeg) + pipeline end-to-end ra video 1080×1920 đạt −14 LUFS, QA gate pass. Xem `CHANGELOG.md`.
- **Chưa tích hợp vào editor của bạn** — đó là việc của Codex theo `CODEX_START_HERE.md`.

## Dựng một video bằng một lệnh
```powershell
python scripts/shorts.py edit "D:\clip\talk.mp4" --instruction "cắt đoạn thừa, phụ đề động, zoom vừa phải"
#   --transcript talk.srt   (hoặc cài faster-whisper để tự nhận dạng giọng nói)
#   --detach  rồi  python scripts/shorts.py status "D:\clip\talk_shorts"
```
Kết quả: `D:\clip\talk_shorts\ai-edit\rev-<n>\final.mp4` + `run-report.json` + `contact_sheet.png`. File gốc không bị đụng tới.

## Dùng với OpenCode
```powershell
python scripts/install_opencode.py "D:\Videos\KenhCuaToi"   # chép gói vào .opencode/skills, thêm lệnh /shorts, /shorts-status
```
Trong OpenCode: `/shorts dựng talk.mp4 theo phong cách Shorts, nhẹ nhàng, chỉ đăng TikTok`. Agent làm theo `AGENTS.md` (không ghi đè, không tự cài thư viện/nhạc khi chưa hỏi). Không sửa `opencode.json` sẵn có — chỉ in đoạn cần thêm.

## Đọc theo thứ tự
1. `00-ASSESSMENT.md` — đánh giá V1.1, khoảng trống, xếp hạng, AI vs không-AI, kiến trúc, lộ trình.
2. `CODEX_START_HERE.md` — prompt giao việc cho Codex.
3. `core/README.md` + `core/references/contracts.md` — hợp đồng dữ liệu chung.
4. `orchestrator/SKILL.md` — điều phối.
5. `skills/0x-*/SKILL.md` — từng Skill.

## Cấu trúc
```
shorts-ai-editing-skills/
├─ 00-ASSESSMENT.md  CODEX_START_HERE.md  PACKAGE-MANIFEST.md  install.ps1
├─ skills.registry.json            ← bật/tắt từng Skill
├─ core/                           ← schema chung, validator, timeline, Unicode
├─ orchestrator/                   ← AI Editing Orchestrator
├─ skills/
│  ├─ 01-editing-director/         ├─ 05-advanced-transitions/
│  ├─ 02-smart-captions/           ├─ 06-cinematic-vfx/ (opt-in)
│  ├─ 03-camera-movement/          ├─ 07-audio-director/
│  └─ 04-smart-cut-pacing/         └─ 08-visual-quality-reviewer/
├─ tools/   subject_boxes.py (OpenCV, tuỳ chọn) · trend_research.py (YouTube API, metadata) · fetch_stock.py (Pexels/Pixabay)
├─ AGENTS.md  opencode/ (lệnh /shorts, cấu hình mẫu)  install-opencode.ps1
└─ scripts/  shorts.py (CLI) · install_opencode.py · doctor.py · check_all.py · run_pipeline_demo.py
```
Gói nằm **cạnh** thư mục `shorts-motion-designer` (V1.1) và tái sử dụng schema `ShortsMotionPlan` của nó; không sửa file nào của V1.1.

## Chạy kiểm tra (Windows PowerShell, trong thư mục gói)
```powershell
python scripts/doctor.py                        # kiểm tra máy: FFmpeg, libass, xfade, font, OpenCV → doctor-report.json
python scripts/check_all.py                     # cấu trúc + schema + toàn bộ test (FFmpeg test tự skip nếu không có ffmpeg)
python scripts/run_pipeline_demo.py             # lập plan cho lệnh mẫu, ghi vào _demo_out/rev-N/
python scripts/run_pipeline_demo.py --render    # + render clip tổng hợp 9:16 thật, QA, contact sheet
```
Yêu cầu: Python ≥ 3.9; FFmpeg ≥ 6.0 có libass (để burn phụ đề ASS) trong PATH.

## Bật / tắt / rollback
- `skills.registry.json` → `"enabled": false` cho Skill bất kỳ. VFX mặc định tắt.
- Mọi lần chạy ghi vào `rev-<n>/` mới; không ghi đè nguồn hay revision cũ. Tắt tất cả Skill ⇒ editor chạy đường cũ.
