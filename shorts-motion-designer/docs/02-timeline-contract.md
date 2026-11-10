# 02 — Timeline, tọa độ và dữ liệu trung gian

## `ShortsMotionPlan` (đề xuất)

`schemas/shorts-motion-plan.schema.json` là **định dạng trao đổi** giúp Codex chuyển intent sang engine đích; không phải engine runtime.

- `video`: `width`, `height`, `fps`, `durationSec` của output.
- `safeArea`: tọa độ normalized `[0..1]` `left/right/top/bottom`; tùy video, UI overlay và bounding box chủ thể.
- `cues`: word/phrase subtitle với `startSec`, `endSec`, `text`, optional `emphasis`/`confidence`.
- `elements`: text/shape/group overlay có `startSec`, `endSec`, `zIndex`, `anchor`, `position`, `styles`, `animations`.
- `animations`: property, `from`, `to`, `startSec`, `durationSec`, easing; **chỉ giới hạn properties engine hỗ trợ sau mapping**.

## Hợp đồng thời gian

- Mọi time trong file interchange là **giây (floating-point)**, tính từ đầu output đã cắt ghép, không phải từ video gốc.
- Tại render, quy đổi bằng chính `fps` của output. Một lựa chọn: `frame = Math.round(t * fps)`; tất cả module phải dùng **cùng** quy ước và có kiểm thử frame biên.
- Cues dạng `[startSec,endSec)` để tránh đè 2 từ tại frame biên; audio cue có thể được giữ ở millisecond nhưng render text phải lượng tử hóa nhất quán.
- Cut/trim/reorder thay đổi timestamp: cần map timestamps transcript về **output timeline**; không dùng timestamp video gốc sau khi ghép.
- Nếu nguồn variable frame rate, normalize hoặc xây timestamp mapping trước khi bám animation vào frame.
- Hạn chế accumulated drift: không cộng `frame += 1/fps` lặp lại rồi chuyển sang audio position; dùng sample/frame index dựa vào origin.

## Hệ tọa độ

- Bố cục chia tỷ lệ normalized: `x=0..1` từ trái qua phải, `y=0..1` từ trên xuống dưới; size trong tỷ lệ kích thước output. Adapter chuyển thành pixel/canvas/SVG units.
- Xác định rõ anchor (center/top-left), pivot và thứ tự transform trước khi tích hợp parenting.
- Layer stacking theo `zIndex` ổn định. Không dùng key order của JSON để suy ra stacking nếu editor không đảm bảo.
- Safe area là cấu hình; không xem một giá trị cố định là đúng cho mọi nền tảng và mọi gương mặt.

## Keyframe, easing, alpha

- `linear`, `ease-in`, `ease-out`, `ease-in-out` có thể map sang easing Remotion/FFmpeg/Canvas tương ứng.
- `position`, `scale`, `rotation`, `opacity`: scale dimensionless, rotation degrees, opacity 0..1. Adapter cần xác định nếu engine dùng radians hoặc scalar percent.
- Không tạo preset làm thay đổi giá trị thuộc tính có xung đột mà không có thứ tự giải quyết công khai.
- Overlay alpha phải được giữ trong render trung gian nếu dùng FFmpeg compositing; test pixel transparency, không chỉ quan sát video final.

## Grapheme và font

- Tách ký tự tiếng Việt theo **grapheme cluster** thay vì `.split('')`; cân nhắc `Intl.Segmenter` nếu môi trường hỗ trợ.
- Word timings đến từ transcript aligner được kiểm chứng; dấu câu và khoảng trắng không được tạo cue sai.
- Có fallback font local hỗ trợ đầy đủ dấu, kích cỡ và line wrap. Browser/FFmpeg/Remotion có thể khác metrics, cần test render cuối.
- Caption dài: chủ động line-break, tối đa số dòng cấu hình, không cắt text ngoài viewport.

## Ví dụ

`../examples/shorts-motion-plan.example.json` minh họa data interchange. **Không được giả định có thể import trực tiếp vào renderer của tool Shorts mà không viết adapter.**
