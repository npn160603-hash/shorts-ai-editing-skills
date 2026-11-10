# Danh mục VFX theo chi phí & engine

| effect | Engine v1 | Cap cần | Chi phí/giây | Dùng khi | Không dùng |
|---|---|---|---|---|---|
| color-accent (eq) | FFmpeg | vfx.colorAdjust | 1 | Look thống nhất cả video | Footage đã grade |
| vignette | FFmpeg | vfx.colorAdjust | 1 | Hướng mắt vào giữa, talking head | Screen recording |
| flash-accent | FFmpeg | vfx.colorAdjust | 1 | Nháy sáng nhẹ ≤ 0.4 s ở climax (fallback rẻ của glow) | Người nhạy cảm ánh sáng: biên độ ≤ 0.12, không lặp < 2 s |
| soft-glow (gblur + screen) | FFmpeg | vfx.glow | 4 | 1–2 lần/video ở climax | Lời dày, sincere |
| focus-blur (gblur) | FFmpeg | vfx.blur | 2.5 | Làm mờ nền khi callout lớn chiếm màn | Khi mặt người là nội dung chính |
| motion-blur (tmix) | FFmpeg | vfx.motionBlur | 3 | Trong swipe/zoom nhanh tự dựng | Footage tĩnh (vô ích) |
| light-sweep | Overlay renderer | overlay.alpha | 3 | Quét sáng qua chữ/logo | FFmpeg-only path (v1 không phát) |
| mask-reveal | Overlay renderer | vfx.mask | 3 | Hiện card/ảnh theo mask | FFmpeg-only path |

Ghi chú hiệu năng: `enable=` chỉ bật hiệu ứng trong cửa sổ, nhưng `split/gblur` vẫn tính mỗi frame → với máy yếu, render riêng đoạn có glow rồi ghép, hoặc đặt `hardwareBudget` để skill tự bỏ hiệu ứng window.

An toàn thị giác: không flash > 3 lần/giây; độ sáng thay đổi ≤ 12%; không dùng đỏ bão hoà nhấp nháy.
