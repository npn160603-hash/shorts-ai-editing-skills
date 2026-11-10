# Tích hợp Skill 03

1. Audit: editor có bước biến đổi video nền không? FFmpeg → thêm chuỗi `ffmpeg_filter()` vào **đầu** filter video sau concat. Remotion/Canvas → áp transform layer từ `sample()`.
2. Manifest: `camera.transform = implemented` sau khi render được 1 clip test; `camera.subpixel = implemented` chỉ với engine transform float.
3. Thứ tự compositing: base video → camera → VFX nền → caption/overlay → export.
4. Toggle: `camera-movement.enabled=false` ⇒ bỏ filter, không đổi gì khác.
5. Test editor: clip 1080×1920 12–20 s; trích frame trước/sau mỗi move; so `state_at` với kích thước vật thể đo được (zoom 1.12 ⇒ vật thể to hơn ~12%).
