# 07 — Motion recipes độc lập (không phụ thuộc thư viện riêng)

Các công thức dưới đây mô tả **nguyên lý** để Codex triển khai bằng engine sẵn có. Không phải source plugin đã chạy. Các tham số, function và ví dụ chỉ mang tính diễn giải.

## A. Frame-based interpolation

Cho FPS output `F`, playhead frame `n`, animation bắt đầu `t0` giây và kéo dài `d > 0`:

```text
u = clamp(((n / F) - t0) / d, 0, 1)
linear(u)      = u
easeIn(u)      = u*u
easeOut(u)     = 1-(1-u)*(1-u)
easeInOut(u)   = u<0.5 ? 2*u*u : 1-2*(1-u)*(1-u)
value(n)       = start + (end-start)*easing(u)
```

- Frame sau điểm kết thúc lấy giá trị cuối (hoặc hành vi hold/reset được định nghĩa rõ trong plan).
- Duration/opacity không hợp lệ phải được validator phát hiện; opacity clamp trong `[0,1]`.
- Vùng thời gian hiển thị của element và vùng thời gian animation phải được kiểm chứng nhất quán.
- Dùng output timeline sau trim/reorder, tuyệt đối không giả định source timestamp còn nguyên.

## B. Primitive animations

- `fade-in`: opacity 0 → 1; 0.2–0.4s, ease-out.
- `slide-up`: y=baseY+offset → baseY đồng thời opacity 0 → 1.
- `scale-pop`: scale 0.85 → 1.0; tránh overshoot quá mức trên caption liên tục.
- `rotate-in`: rotation -4° → 0°, opacity 0 → 1; phù hợp graphic card, ít dùng cho subtitle.
- `fade-out`: opacity 1 → 0, điều kiện end frame và element lifetime rõ ràng.
- `stagger`: offset start `t_i = t0+i*delay`; giữ nguyên thứ tự hiển thị, không xáo trộn theo render pass.

## C. Group/parenting (optional advanced feature)

- Mỗi child có `parentId`; chỉ parent là group, ID duy nhất, không tồn tại vòng lặp.
- Child position/rotation/scale là *local*; final transform = parent world matrix × child local matrix. Xác định anchor/pivot, thứ tự translate/rotate/scale và test với nested groups.
- Nếu dùng SVG, tạo group `<g>` và nested transform thích hợp; nếu FFmpeg-only, có thể render group thành transparent overlay rồi chuyển động cả overlay.
- Group opacity và child opacity cần compositing đúng; nhân opacity đơn giản chỉ đúng trong một số cấu hình render.
- Không xây parenting trước khi M1 đạt, trừ khi editor có sẵn.

## D. Typography & captions

- Whole line: một layer, dễ render nhất.
- By word: tách từ, giữ punctuation kèm từ, giữ khoảng trắng khi layout; không tự phỏng đoán word timings.
- By grapheme: dùng `Intl.Segmenter(locale, {granularity:'grapheme'})` nếu JS runtime có; trong Python tìm thư viện Unicode phù hợp hoặc fallback whole-word, không dùng `.split('')` với tiếng Việt.
- Chỉ highlight từng từ theo giọng nói nếu transcript đã có cue `start/end` theo từng từ, được map qua cuts.
- Hạn chế caption 1–2 dòng, test đo kích thước text ở chính engine export, kiểm tra safe area và visual subject bbox.

## E. Preset library schema ideas

- Preset chỉ khai báo các operation trong whitelist (`opacity`, `position.x`, `position.y`, `scale`, `rotation`).
- Có `id`, tham số, mặc định, duration, easing, delay; import JSON local nhưng **không eval JS**.
- Nếu 2 preset đụng property tại cùng thời gian, chọn quy tắc xác định: reject conflict hoặc priority order minh bạch. Custom keyframe có precedence chỉ khi được ghi rõ.
- Chạy test định tính: frame start/middle/end, mỗi clip cho kết quả deterministic.

## F. Đặc thù compositing

- Render overlay nền transparent thật (RGBA), không black plate giả alpha. MP4 H.264 tiêu chuẩn không thích hợp làm intermediate alpha nếu không dùng codec chuyên dụng được test.
- Cùng resolution/FPS/timeline offset với output video, bảo toàn audio.
- Khi client preview dùng một engine còn export dùng engine khác, phải có visual diff hoặc ít nhất frame review.

## G. Hiệu ứng chưa phải năng lực mặc định

Mask/clipping, glow, 2.5D camera, motion blur, background removal, beat sync, face tracking và AI semantic editing cần có runtime tương ứng. Nếu chưa có, báo rõ chưa hỗ trợ và đưa kế hoạch, không tuyên bố Skill cung cấp sẵn.
