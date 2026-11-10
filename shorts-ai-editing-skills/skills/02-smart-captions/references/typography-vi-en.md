# Typography phụ đề cho tiếng Việt & tiếng Anh

## Unicode
- Luôn **NFC** trước khi đo/vẽ (ASR và clipboard hay trả NFD: "ế" = e + ̂ + ́). `sae_text.nfc()`.
- Animation theo ký tự phải theo **grapheme** (`sae_text.graphemes`, hoặc `Intl.Segmenter` trong JS). Không `list(str)`.
- Font phải có đủ dấu chồng (ẫ, ặ, ỡ…). Gợi ý OFL: Be Vietnam Pro, Montserrat (bản có Vietnamese), Inter, Noto Sans. QA kiểm "tofu" (ô vuông).
- Dấu trên chữ hoa (Ấ, Ể) cao hơn: `lineHeight` ≥ 1.15 để dòng trên không chạm dấu dòng dưới.

## Ngắt dòng & ngắt trang
- Tối đa 2 dòng (Shorts), mỗi dòng ≤ ~90% bề rộng safe area.
- Không tách: số + đơn vị ("25 phút"), từ ghép ("lãng phí", "thời gian" — xem `VI_COMPOUNDS` + `vi-compounds.txt`), dấu câu đứng riêng.
- Ưu tiên ngắt sau dấu câu; tránh dòng/trang chỉ 1 từ (trừ style punchy).
- Tiếng Anh: không tách "Mr. Smith", số + unit, tính từ + danh từ ngắn nếu được.
- Tiếng Việt dài hơn tiếng Anh ~15–25% số ký tự cho cùng ý → `maxCps` VI nên 15–17, EN 17–20.

## Tốc độ đọc
- CPS (ký tự không tính khoảng trắng / giây) > `maxCps` → cảnh báo; không làm chậm lời, chỉ có thể giảm số chữ/trang.
- Thời gian tối thiểu một trang: 0.5 s (standard), 0.35 s (punchy), 0.7 s (calm).

## Tương phản
- Viền ≥ 5 px ở 1080p hoặc hộp nền alpha ≥ 50% khi footage sáng/nhiều chi tiết.
- Màu nhấn duy nhất cho cả video (vàng #FFD400 mặc định). Không dùng đỏ/xanh lá thuần làm chữ chính.
