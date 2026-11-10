---
name: advanced-transitions
description: >-
  Chọn chuyển cảnh theo nội dung cho Shorts (cut, smooth cut, swipe, zoom, blur, mask/shape reveal,
  directional) ở từng ranh giới cắt; transition mượn handle từ đoạn đã cắt nên không đổi thời lượng,
  không dời lời nói; xuất TransitionPlan và filter FFmpeg xfade đã kiểm chứng.
---

# Skill 05 — Advanced Video Transitions

## 1. Mục đích
Làm ranh giới cảnh mượt hoặc có chủ đích **mà không lạm dụng**, không phá đồng bộ lời/phụ đề.

## 2. Khi nào dùng
Sau Skill 04 + Camera, khi có ranh giới đổi ý/đổi cảnh và người dùng muốn dựng "chuyên nghiệp".

## 3. Khi nào không dùng
Jump cut trong cùng một shot (để camera reframe xử lý); trong hook; khi lời nói liền mạch qua điểm cắt; video phong cách tối giản.

## 4. Đầu vào
CutList, khoảng lời nói output time (từ word timestamps hoặc segment), DirectorDecisions (vai trò đoạn kế), CameraTrack, scene changes (tuỳ chọn), ngân sách, capability `transition.xfade`.

## 5. Đầu ra
`TransitionPlan` (`schemas/transition-plan.schema.json`) — mỗi ranh giới một mục kèm **lý do** (kể cả lý do không dùng); `ffmpeg_graph()` → `[vout][aout]`.

## 6. Quy trình
1. Liệt kê ranh giới từ CutList; phân loại `jump-cut | section | scene`.
2. Chọn type theo vai trò đoạn sau (point → swipe-left, climax → zoom, CTA → smooth-cut…).
3. Loại nếu: hook, thiếu handle, lời ở nửa giữa cửa sổ, camera move trong cửa sổ, bị cấm.
4. Ưu tiên theo điểm, cắt theo `maxVisualTransitions`.
5. Render: trim frame-exact + handle, concat theo nhóm, `xfade` giữa nhóm; audio concat như không có transition.

## 7. Công cụ
FFmpeg ≥ 6.0 (`xfade`, `settb`, `fps`). Python stdlib. Đã kiểm: output 423 frame = đúng thời lượng bản không transition.

## 8. Preset
`CATALOG` trong `lib/transitions.py`; quy tắc trong `references/transition-catalog.md`.

## 9. Phối hợp
Camera thắng transition (CR-02). Audio (Skill 07) có thể gắn 1 SFX whoosh vào transition visual (nếu được phép). QA kiểm số lượng/độ nhất quán kiểu transition.

## 10. Nghiệm thu
- `python tests/test_transitions.py` pass (render thật, so số frame & thời lượng audio với bản cut thường).
- Không transition trong 2 s đầu; ≤ ngân sách; caption vẫn khớp lời sau transition (frame review tại ranh giới).

## 11. Giới hạn
- `xfade` cần cả video re-encode; tốn CPU hơn concat.
- Motion match, light-leak, transition theo mask chủ thể: cần AI/CV hoặc asset có license → không có trong v1.
- Nguồn VFR phải chuẩn hoá CFR trước (trim theo frame).

## 12. Fallback
Không xfade → toàn bộ hard cut (+ fade audio 10 ms). Skill tắt → giống output Skill 04.
