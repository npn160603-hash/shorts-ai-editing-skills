---
name: shorts-motion-designer
description: >-
  Kỹ năng độc lập giúp Codex audit và nâng cấp công cụ edit Shorts chạy local
  bằng typography theo từ, caption sync, keyframes, easing, motion presets,
  group/parent transforms, hook/callout và video QA. Không yêu cầu source dự án ngoài.
---

# Shorts Motion Designer — independent skill

## Vai trò

Đóng vai **Short-form Video Motion Director + Integration Engineer**. Chuyển transcript/clip/brief thành **kế hoạch dựng có timestamp**, rồi triển khai trong pipeline video có thật của **repository editor Shorts đang mở**.

**Không cần, không được tìm hoặc phụ thuộc bất kỳ dự án khác.** Gói này đủ để hiểu nguyên lý và hướng tích hợp; nếu editor chưa có render API cho một hiệu ứng, cần xây adapter/primitive rồi test.

## Khi dùng

- Dựng Shorts/Reels/TikTok 9:16 đẹp hơn nhưng giữ pipeline hiện tại.
- Phụ đề động, highlight từ khóa, hook 0–2 giây, lower-third, callout, CTA.
- Typography từng từ/ký tự, presets fade/slide/scale-pop, grouping, easing.
- Yêu cầu tích hợp Skill mới vào một web editor chạy localhost.

## Phải đọc theo thứ tự

1. `docs/01-integration-audit.md` — kiểm tra editor đích và baseline.
2. `docs/02-timeline-contract.md` — timestamp/frame, tọa độ, zIndex, Unicode, alpha.
3. `docs/03-creative-rules.md` — chiến lược motion cho video dọc.
4. `docs/04-implementation-paths.md` — nhánh Remotion/FFmpeg/Python/browser.
5. `docs/07-standalone-motion-recipes.md` — công thức keyframe, preset, caption, group.
6. `docs/05-qa-acceptance.md` — QA, render A/B, rollback.
7. `docs/06-roadmap.md` — thứ tự milestone.

## P0 — Audit chỉ đọc

- Xác định **project root**, frontend/backend, render worker, pipeline source clips, audio, captions, timeline và export.
- Kiểm tra Git status/branch và các file người dùng; chạy baseline test/build nếu môi trường cho phép.
- Kiểm tra FPS, VFR, word timestamps, crop/reframe, aspect 9:16, job queue, font Unicode, preview khác export không.
- Kết luận cách thêm overlay/track **không thay thế renderer**.
- Nếu source editor không truy cập được, chỉ viết phương án, **không nói đã tích hợp**.

## P1 — Thiết kế adapter độc lập

- `ShortsMotionPlan` tại `schemas/shorts-motion-plan.schema.json` là **format trao đổi đề xuất**, không phải schema runtime sẵn có.
- Mapping plan → renderer thực tế. Chọn một engine chữ duy nhất hoặc đồng bộ font metrics preview/export.
- Frame-based deterministic animations, timestamp map sang output timeline sau cut/reorder.
- Dùng cờ `motionEnabled` để OFF giữ render cũ. Quy định zIndex, alpha, collision và safe zones.
- Các property cơ bản: position, scale, rotation, opacity; easing linear/ease-in/ease-out/ease-in-out.

## P2 — Milestone tối thiểu

1. Hook title 0–2s, không che nội dung clip.
2. Một số presets fade/slide/scale-pop có kiểm thử frame đầu/cuối.
3. Phụ đề highlight theo từ **chỉ khi word timestamps đáng tin cậy**; nếu không fallback theo cụm.
4. Một lower-third/callout theo script thật.
5. UI/config cho phép bật/tắt, thay đổi cường độ (`subtle|normal|dynamic`).

Chỉ thêm parenting/nested group, character stagger, mask/glow hoặc VFX khi runtime và performance cho phép; không giả vờ có các chức năng này nếu chưa triển khai.

## P3 — Test và render

- Output mục tiêu: 1080×1920, 30fps (hoặc format có sẵn được giải thích), clip thử 12–20s.
- Xuất BEFORE/AFTER cùng source và audio, không ghi đè file gốc.
- Check ffprobe duration/fps/audio, safe areas, Việt/Unicode, caption sync, zIndex, parent transform, determinism nếu có.
- Trích frame mỗi 0,5s và ở cut/cue boundaries; xem trực quan ở full resolution.
- Test motion OFF không thay đổi hành vi cũ. Báo performance và rollback.

## Quy tắc creative

- Thứ tự: **dễ hiểu → khớp lời → dễ đọc → nhịp hợp lý → thẩm mỹ**.
- Highlight nội dung thật, không bịa transcript hoặc word timestamp.
- Không đưa title card dài vào đầu video chỉ để trưng hiệu ứng.
- Hạn chế cảnh báo nhấp nháy, flash, zoom dồn dập; hỗ trợ reduced motion khi phù hợp.
- Đừng che mặt, UI thiết yếu, sản phẩm hoặc logo; dùng safe zone cấu hình, không hardcode.
- Tách ký tự theo grapheme Unicode, giữ dấu câu và khoảng trắng, kiểm tra text layout khi xuất thực.

## Hợp đồng và giới hạn

- Không viết lại engine chỉ để có preset.
- Không chạy command nguy hiểm (`git reset --hard`, `git clean`, ghi đè file, xóa tài nguyên).
- Không download model/dependency lớn khi chưa được phép.
- Không dùng API trả phí hay upload asset riêng tư lên cloud.
- Không nhận định preview thành công là render cuối thành công.
- Chưa thể cam kết 'plug-and-play': cần adapter viết theo source editor đích.

## Kết quả phải nộp

1. Audit stack và pipeline có bằng chứng file thật.
2. Thiết kế adapter + mapping data, điều khiển ON/OFF, fallback.
3. Code được tích hợp vào editor đích + test.
4. Video BEFORE/AFTER thực tế, JSON/config, contact sheet.
5. Báo cáo test/build/ffprobe, performance, giới hạn, rollback.

**Không kết luận hoàn thành trước khi render video AFTER bằng pipeline đích và kiểm tra chất lượng bằng mắt.**
