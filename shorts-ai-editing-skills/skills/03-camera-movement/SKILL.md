---
name: camera-movement
description: >-
  Camera ảo cho Shorts: smooth zoom, punch-in/out, reframe che jump cut, pan theo chủ thể, reframe
  16:9→9:16, shake có kiểm soát — tất định, không bao giờ lộ viền, giới hạn zoom theo độ phân giải
  nguồn; xuất CameraTrack + chuỗi lọc FFmpeg đã kiểm chứng hoặc keyframe cho Remotion/Canvas.
---

# Skill 03 — Cinematic Camera Movement

## 1. Mục đích
Tạo chuyển động máy quay trên video nền (base layer) theo quyết định của Director, chỉ với những gì engine đích **thực sự render được**.

## 2. Khi nào dùng
Có `DirectorDecisions` với accent camera; `camera.transform` = implemented; người dùng yêu cầu zoom/nhấn.

## 3. Khi nào không dùng
- Nguồn đã thấp phân giải hơn khung ra (zoom tự tắt).
- Screen recording có chữ nhỏ (zoom làm vỡ chữ) — trừ khi zoom để đọc rõ vùng chữ có box.
- Video đã có chuyển động máy mạnh (handheld) → chỉ punch-in tĩnh, không shake.

## 4. Đầu vào
`DirectorDecisions` (smooth-push / punch-in / jump-cut-reframe), kích thước nguồn + đầu ra + fps, điểm cut (output time), mode từ Orchestrator, tuỳ chọn subject boxes.

## 5. Đầu ra
`CameraTrack` (`schemas/camera-track.schema.json`), chuỗi lọc FFmpeg (`ffmpeg_filter`), mẫu theo frame (`sample`).

## 6. Quy trình
1. Tính base window (tỉ lệ đầu ra) và `maxZoom` theo độ phân giải.
2. Duyệt accent theo thời gian → move: smooth-zoom (ease-in-out), punch-in (step) + release, reframe-step tại cut.
3. Tâm cửa sổ: theo subject box (mắt ở đường 1/3 trên) hoặc center-weighted.
4. Áp CR-01 (không chồng move); cap zoom; cảnh báo move chậm trên engine pixel nguyên.
5. Xuất theo engine (`references/engine-mapping.md`).

## 7. Công cụ
FFmpeg (scale eval=frame + crop) hoặc renderer có transform (Remotion/Canvas). Python stdlib.

## 8. Preset
Easing dùng chung `core/lib/sae_easing.py` (thêm `back-out` cho punch có nảy nhẹ). `examples/camera-presets.json` (có cột `engineSupport`): smooth-zoom-in/out, punch-in/out, pan-to-subject, dynamic-reframe, impact-shake (cấm mặc định), parallax-2_5d (**chỉ tài liệu**, cần AI mask/depth).

## 9. Phối hợp
- Director quyết định *khi nào*; Camera quyết định *thế nào*.
- Transitions đọc zoom hai bên cut (CR-02: không đổi zoom trong cửa sổ transition).
- Caption/overlay composite sau camera (CR-04).

## 10. Nghiệm thu
- `python tests/test_camera.py` pass (render FFmpeg thật, kích thước không đổi, frame zoom khác nguồn, frame không zoom gần như trùng nguồn).
- Không frame nào có viền đen (kiểm `blackdetect` vùng mép hoặc soi contact sheet).
- Zoom thực tế ≤ `maxZoom`; mặt chủ thể nằm trọn trong khung khi có box.

## 11. Giới hạn
- FFmpeg crop pixel nguyên → slow push dài có thể rung nhẹ.
- Phát hiện chủ thể cần `tools/subject_boxes.py` (OpenCV, tuỳ chọn); thiếu thì center-weighted.
- 2.5D parallax, motion-match tracking: cần AI/CV, không có trong runtime v1.

## 12. Fallback
- Không subject box → center-weighted, headroom nhẹ.
- Engine không có transform → bỏ camera, Director accent chuyển sang keyword-pop (không làm gì thêm ở đây).
- Skill tắt → base video giữ nguyên.
