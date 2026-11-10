# 03 — Quy tắc AI Motion Director cho Shorts

## Thứ tự ưu tiên

**Dễ hiểu → nghe/đọc rõ → nhịp hợp nội dung → sự nhất quán → hiệu ứng đẹp.** Không chạy preset liên tục để chứng minh kỹ thuật.

## Những vùng nội dung

- **0–2 giây — Hook:** chọn một câu hoặc từ mạnh đúng transcript; sự thay đổi thị giác đủ để thu hút, không phải title card che mất nội dung 2 giây.
- **2–8 giây — Build:** cắt nhịp theo câu, highlight 1–2 keyword/segment; tránh chữ và graphic tranh vị trí với chủ thể.
- **Giữa clip — Reinforce:** chỉ thêm callout/card khi có số liệu/ý tưởng đáng nhấn, tránh popup mỗi câu.
- **Cuối — Payoff/CTA:** cho người xem đủ thời gian đọc câu kết; không chèn CTA khi nội dung còn đang dở.

Những mốc trên là heuristic, **không** một timeline cứng; video 10 giây, 20 giây hay 60 giây cần pacing khác nhau.

## Preset khi nào dùng

| Preset idea | Tác dụng | Lưu ý |
|---|---|---|
| `caption-word-highlight` | nhấn từ đang nói | chỉ khi có word timestamps |
| `hook-reveal` | mở đầu bắt mắt | không che chủ thể/thông tin |
| `soft-slide-up` | caption/callout xuất hiện | ngắn, dễ đọc |
| `scale-pop` | keyword/số liệu mạnh | hạn chế liên tục, tránh giật |
| `stagger-words` | kinetic typography | không phá line-wrap và dấu Việt |
| `lower-third` | nhãn/cụm định danh | ổn định và vừa đủ |
| `outro-lockup` | kết video | không ép nếu clip cần kết nhanh |

## Phụ đề

- Văn bản dựa trên transcript thật và cue sync; không bịa đoạn nói.
- Highlight tối đa một đoạn ngắn ở thời điểm phù hợp.
- Giữ tương phản cao, shadow/stroke nền khi cần, và màu nhấn thống nhất.
- Không đè mặt, product demo, logo thương hiệu; định nghĩa exclusion zones khi editor có bounding box.
- Thích ứng theo vị trí caption hiện có của editor, không buộc text chạy ở một y cố định.

## Kiểm tra hậu kỳ

- Xem clip với âm thanh thật, kể cả lúc mute để thử readability.
- Kiểm tra trên canvas dọc kích thước nhỏ; chữ trên laptop to chưa chắc điện thoại đọc được.
- Kiểm tra đoạn ngắt lời/đổi chủ thể/cắt shot; effect không được kéo dài qua cut một cách vô ý.
- Cho phép user điều chỉnh `motionIntensity = subtle|normal|dynamic` qua config, không hardcode một style duy nhất.

## Thiết kế ưu tiên mobile

- 1080×1920, nhưng render đúng aspect bất kỳ.
- Typography visual hierarchy: hook > spoken captions > decoration.
- Tránh chuyển động quá nhanh, flicker, flash; hỗ trợ reduced-motion mode khi preview/tool có tùy chọn.
