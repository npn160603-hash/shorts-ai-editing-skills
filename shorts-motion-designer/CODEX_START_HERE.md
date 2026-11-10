# PROMPT CHO CODEX — NÂNG CẤP TOOL EDIT SHORTS ĐỘC LẬP

> Mở Codex ngay trong **thư mục gốc của công cụ edit video Shorts chạy localhost trên máy hiện tại**. Gói `shorts-motion-designer` giải nén ở một thư mục bất kỳ. Đọc `SKILL.md` bằng đường dẫn thực tế trước khi sửa mã nguồn.

Bạn là Senior Video Editing Systems Engineer, Motion Graphics Engineer và AI Editing Director.

## Phạm vi

Tôi có **một công cụ riêng** tự động edit video Shorts chạy trên web localhost. Đây là dự án độc lập. **Không có và không cần codebase nào khác**. Mọi thao tác, khảo sát và tích hợp chỉ dựa trên source của công cụ đang mở và gói Skill này.

**Gói Skill:** `PATH_TO_PACKAGE/SKILL.md` — thay bằng đường dẫn thật tới file `SKILL.md` trong folder giải nén. Các tài liệu liên quan nằm ngay trong cùng folder.

Đọc `SKILL.md`, `docs/01-integration-audit.md`, `docs/02-timeline-contract.md`, `docs/03-creative-rules.md`, `docs/04-implementation-paths.md`, `docs/07-standalone-motion-recipes.md`, `docs/05-qa-acceptance.md` trước khi thay đổi code.

## Bước 1 — Chỉ đọc, audit tool thật

- Xác định project root hiện tại, frontend/backend và stack render: Remotion, FFmpeg, Python, OpenCV, Canvas, WebCodecs hoặc công nghệ khác.
- Kiểm tra source clip, audio, subtitles, cut/trim, timeline, word timestamps, crop/reframe, preview/export, job queue và đường dẫn output.
- Kiểm tra Git status, baseline test/build; bảo vệ file chưa commit và user settings.
- Viết `docs/shorts-motion-integration-audit.md` trong project đích với bảng: tính năng hiện tại | tính năng cần thêm | cách triển khai | rủi ro | test.

## Bước 2 — Thiết kế tích hợp tối thiểu

- Sử dụng module, thư viện, pattern đã có **trong chính tool** nếu phù hợp.
- Đọc schema/ví dụ plan trong gói Skill, thiết kế adapter chuyển plan thành renderer runtime thực tế; không assume JSON ví dụ nạp thẳng được.
- Giữ nguyên audio/source clips, time remapping và export pipeline, chỉ thêm overlay/animation có thể bật/tắt.
- Mọi animation deterministic theo frame/timestamp, không dùng clock ngẫu nhiên.
- Trình bày ngắn quyết định stack, z-order, font tiếng Việt, safe-area, perf, fallback và rollback.

## Bước 3 — Triển khai Milestone 1

1. Hook title ngắn trong 0–2 giây.
2. 2–3 preset motion cơ bản (fade, slide, scale-pop).
3. Phụ đề động/highlight theo từ **nếu dữ liệu word timing tồn tại**; nếu không, dùng phrase-level, không tự bịa timestamp.
4. Callout/lower-third khi nội dung cần nhấn mạnh.
5. Config hoặc UI bật/tắt `motionEnabled`; OFF phải giữ hành vi hiện có.
6. Có test validation, timeline và khớp audio/video. Tránh xây VFX/camera/group phức tạp ở milestone đầu.

## Bước 4 — Kiểm thử bằng video thực

- Render BEFORE (motion OFF) và AFTER (motion ON) từ cùng một clip nguồn 12–20 giây, 9:16. Dùng media demo local hợp lệ nếu không có input người dùng.
- Ưu tiên 1080×1920, 30fps nếu engine hỗ trợ.
- Kiểm tra metadata ffprobe, đồng bộ lời/phụ đề, không che mặt/visual chính, chữ tiếng Việt và Unicode, không làm hỏng audio.
- Trích contact sheet mỗi 0,5s + frame tại cut/cue boundary; nhìn và sửa lỗi trước khi báo đạt.
- Chạy tất cả test/build liên quan; ghi lại kết quả thật, không chỉ đưa lời cam kết.

## Bước 5 — Báo cáo

Gồm: (1) stack thật của tool; (2) file đã sửa/thêm; (3) adapter và những hiệu ứng hoạt động; (4) link path absolute video BEFORE/AFTER và config; (5) test/build/ffprobe; (6) rủi ro/performance; (7) cách tắt/rollback; (8) tính năng kế tiếp nếu chất lượng M1 đạt.

**Ràng buộc:** Không xóa/reset/clean/stash, không tự ý đổi engine toàn hệ thống, không tải dependency/model mới chưa được chấp thuận, không API trả phí/đưa asset lên mạng, không ghi đè video cũ, không push remote. Không tuyên bố đã tích hợp nếu chưa chạy pipeline render thật.

**Bắt đầu audit và triển khai M1 chỉ khi xác định được cách tích hợp an toàn.**
