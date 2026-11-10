---
name: cinematic-vfx
description: >-
  VFX nhẹ cho Shorts trên lớp video nền: color accent, vignette, soft glow, focus blur, motion blur,
  flash accent — chỉ ở climax, trong ngân sách hiệu năng máy cá nhân, tham số bị kẹp trong whitelist;
  light sweep/mask chỉ khi có overlay renderer. Opt-in (mặc định tắt).
---

# Skill 06 — Cinematic VFX

## 1. Mục đích
Thêm điểm nhấn thị giác **hiếm và có lý do**, không giảm khả năng đọc, chạy được trên máy cá nhân.

## 2. Khi nào dùng
Người dùng yêu cầu VFX/glow/look điện ảnh; registry bật skill; có climax từ Director.

## 3. Khi nào không dùng
Mặc định (skill opt-in); video giáo dục/hướng dẫn cần rõ ràng; đoạn chân thành; máy không đủ ngân sách render; footage đã có nhiều hiệu ứng.

## 4. Đầu vào
DirectorDecisions, trạng thái capability `vfx.*`, intensity, `duration`, `hardwareBudget` (từ manifest `maxRenderSecondsPerOutputSecond`), `forbiddenEffects`.

## 5. Đầu ra
`VfxPlan` (`schemas/vfx-plan.schema.json`) + `ffmpeg_chain()` (một chuỗi `-vf`, đặt sau camera, trước caption).

## 6. Quy trình
1. Global grade nhẹ (nếu cho phép).
2. Với accent thuộc climax: chọn glow (nếu có) hoặc flash-accent; cách nhau ≥ 2 s; tối đa theo intensity (1/2/4).
3. Kẹp tham số vào khoảng whitelist.
4. Ước lượng chi phí/giây; vượt ngân sách → bỏ hiệu ứng window.

## 7. Công cụ
FFmpeg (`eq`, `vignette`, `gblur`, `blend`, `tmix`, timeline `enable`). Overlay renderer (Canvas/Remotion) cho light-sweep/mask.

## 8. Preset
`CATALOG` (tham số min/max/default) — `references/vfx-catalog.md`.

## 9. Phối hợp
Chỉ lớp nền (CR-04: không áp lên caption). Không đặt glow cùng lúc transition (Orchestrator conflict-check). Ưu tiên thấp nhất sau transition (CR-08 priority).

## 10. Nghiệm thu
`python tests/test_vfx.py` pass (render FFmpeg thật); frame review: chữ caption không bị nhoè/loá; số accent ≤ giới hạn; render time đo được ≤ ngân sách.

## 11. Giới hạn
Không có glow theo mask chủ thể, light leak, particles, LUT có bản quyền. Light sweep/mask cần overlay renderer.

## 12. Fallback
Không glow → flash-accent; không capability nào → skill bỏ qua. Tắt → không có filter VFX.
