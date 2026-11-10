# Ngôn ngữ camera ảo cho Shorts

| Kỹ thuật | Ý nghĩa với người xem | Dùng khi | Tránh khi |
|---|---|---|---|
| Smooth zoom in (1.0→1.07, 1–2.5 s) | "Lại gần, chú ý" | Hook, đoạn dẫn tới climax | Đang có transition (CR-02); engine integer-pixel + move > 2.5 s |
| Punch-in (cắt tức thì 1.12) | Nhấn mạnh, đổi nhịp | Đầu ý chính/climax, che jump cut | Lời dày, đoạn chân thành, CTA |
| Punch-out / release | Thả lỏng sau nhấn | Hết segment được nhấn; trùng cut thì cắt thẳng | — |
| Reframe-step tại cut | Che jump cut (hai shot khác cỡ ≥ 6%) | Ranh giới cut sau hook | Hai cut cách nhau < 1 s (gây giật) |
| Pan to subject | Theo chủ thể | Có subject boxes, zoom > 1 | Không có box (đoán vị trí = sai) |
| Dynamic reframe 16:9→9:16 | Giữ chủ thể trong khung dọc | Nguồn ngang | Không có box → crop giữa tĩnh |
| Shake có kiểm soát | Va chạm, "boom" | Hiếm, chỉ intensity dynamic | Mặc định cấm; người say xe; video giáo dục |
| 2.5D parallax | Chiều sâu ảnh tĩnh | B-roll ảnh | Cần mask/depth (AI) — chưa có runtime v1 |

## Giới hạn chất lượng
- `maxZoom = min(1.6, (base_window_h / out_h) × 1.3)`; nguồn ngang 1080p → khung dọc đã phải phóng → **zoom bị tắt**.
- Không bao giờ để cửa sổ ra ngoài khung (clamp) → không viền đen.
- Shake: biên độ ≤ 0.6% khung (schema cấp tối đa 2%), ≤ 0.35 s, có envelope tắt dần, seed lưu trong track (tất định).

## Liên tục
- Mức zoom **giữ** đến move kế tiếp. Punch-in luôn có release (trùng cut → cắt thẳng; không → ease-out 0.25 s).
- Caption không đi theo camera (composite sau, CR-04).
