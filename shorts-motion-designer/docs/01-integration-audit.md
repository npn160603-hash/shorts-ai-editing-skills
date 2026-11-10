# 01 — Audit chính công cụ edit Shorts đang mở

## Câu hỏi bắt buộc

1. Render ở đâu: browser, Node backend, Python worker, FFmpeg CLI hay một engine khác?
2. Timeline dùng frame hay seconds? VFR input được normalize/mapping như thế nào?
3. Data flow: import → decode → trim → crop → audio → captions → overlays → encode.
4. Transcript lấy từ đâu? Word-level timestamps có đáng tin không? Câu bị cắt/reorder map timestamp thế nào?
5. Subtitle burn-in bằng FFmpeg, ASS, Canvas, SVG, CSS, Remotion hay cơ chế khác?
6. Có crop/reframe, bbox/face tracking/exclusion zones không? Có thể tránh đặt chữ lên mặt không?
7. Export codec, audio, fps, size, bitrate, ffprobe, API/CLI, job queue, cache và temp files?
8. Có thể tạo overlay track an toàn mà không viết lại render pipeline không?
9. Có font local hỗ trợ tiếng Việt, kiểm tra Unicode NFC/NFD và 9:16 safe zones chưa?
10. Git status, thay đổi chưa commit, user settings, cách rollback và baseline test/build?

## Bảng quyết định

`feature | editor đang có | thiếu gì | adapter/implementation đề xuất | rủi ro | test`

Chỉ xác nhận tính năng đã có nếu đọc được source hoặc chạy demo kiểm chứng. Không giả định rằng editor 'web chạy localhost' dùng bất cứ framework cụ thể nào.

## Khi nào dừng

- Không chạy baseline/build: báo blocker và giới hạn phạm vi sửa, không tuyên bố thành công.
- Không có word timing: dùng phrase captions, không bịa sync từng từ.
- Không có alpha compositing: thử PNG RGBA overlay/FFmpeg filter trong fixture trước.
- Preview là HTML nhưng export khác engine: kiểm tra render cuối độc lập.
- Chỉ có source frontend và không có pipeline export: thiết kế phương án phù hợp trước khi thay runtime.
- Asset chứa dữ liệu riêng tư: giữ xử lý local, không upload.

**Toàn bộ bằng chứng audit phải đến từ editor đích và chính bộ tài liệu này.**
