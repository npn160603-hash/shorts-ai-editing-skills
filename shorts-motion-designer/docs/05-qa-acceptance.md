# 05 — QA, regression và nghiệm thu

## Milestone 1 phải có

- Motion được bật/tắt bằng feature flag; OFF không làm thay đổi video/audio output cũ ngoài metadata không quan trọng.
- Video test 9:16 1080×1920, 30 FPS hoặc output native đã được giải thích; 12–20 giây.
- Hook/title, caption word-highlight **nếu có alignment**, 1–2 basic presets, ít nhất một card/callout.
- Cùng footage và audio: before/after, cùng duration; không thêm đoạn câm ngoài ý muốn.
- Text tiếng Việt, dấu câu, dài/ngắn, line wraps, Unicode tổ hợp, không bị mất glyph.
- Không có word timestamp: fallback theo phrase, không giả lập sync từng từ.
- Asset/source riêng tư được giữ local.

## Test matrix

| Nhóm | Trường hợp |
|---|---|
| Timeline | frame 0, end-frame, t âm, cue trùng, cue ngoài duration, cut/reorder |
| FPS | 24/25/30/60 fps nếu engine hỗ trợ, vfr input normalize |
| Layout | nhiều dòng, màn 9:16, safe zones, mặt/người, overlap |
| Text | tiếng Việt NFC/NFD, emoji, punctuation, zero-width joins |
| Motion | easing end values, opacity clamp, zIndex, deterministic per frame |
| Composite | RGBA alpha, transparent pixels, no black plate, blend |
| Export | H264 + audio, A/V sync, duration, no aspect distortion |
| Regression | OFF output so với baseline, output path, job queue, cancel/error |
| Performance | render speed, memory, storage and cleanup of temp PNG frames |

## Visual QA

- Trích frame theo 0,5 giây **và** tại cut/cue boundaries.
- Nhìn full-res các frame có chữ nhỏ, tên người, số liệu, đầu/cuối animation.
- Nếu có lỗi, sửa config/adapter và render lại trước khi nghiệm thu.
- Không chấm điểm "đẹp" bằng unit tests đơn thuần; review có tính chủ quan, nêu bằng chứng cụ thể.

## Mẫu báo cáo kết quả

1. Stack và kiến trúc xác minh.
2. Branch/commit + Git status, files thay đổi.
3. Các feature đã hoạt động *bằng demo*, feature chưa có.
4. Test summary, build/typecheck, ffprobe output.
5. A/B videos, scene/config, contact sheets, log output.
6. Performance, ảnh hưởng size render, giới hạn.
7. Điều kiện bật/tắt feature flag và rollback.
8. Lộ trình tiếp theo chỉ sau nghiệm thu.

## Không đủ điều kiện kết luận thành công nếu

- Có chỉ ảnh demo nhưng không có video thật từ pipeline editor đích.
- Cắt ghép chính/audio bị thay đổi ngoài yêu cầu.
- Caption lệch lời thoại vì đoán timestamp.
- Chỉ chạy test schema, chưa kiểm tra visual.
- Đưa cả renderer vào codebase đích mà không có kiểm chứng tích hợp và rollback.
