# Bảng quyết định của Director

Mọi quyết định đều có **lý do đo được** (feature) và đi qua **ngân sách** (`effectBudget`). Không có lý do → không có hiệu ứng.

## Đoạn nào cắt nhanh / giữ lâu
| Tín hiệu | Quyết định | Ghi vào |
|---|---|---|
| Hook (0–~2 s) | `pacing: tighten` — trim đầu tối đa, không pause | `segments[].pacing` |
| `wordsPerSec` > 3.6 (VI) | `hold` — không cắt thêm, tối đa 1 accent | `restraint` |
| Câu hỏi, climax | `protectAfterSec: 0.35` — để người xem "thấm" | Skill 04 chạy lại với protected |
| Khoảnh khắc chân thành (xin lỗi, cảm ơn, khó khăn…) | `hold`, `captionMode: calm`, không accent | `restraint` |
| Đoạn setup bình thường | `normal` | — |

## Đoạn nào zoom
| Loại | Khi nào | Mức (normal) |
|---|---|---|
| `smooth-push` | Suốt hook | 1.0 → ~1.07 |
| `punch-in` | Đầu segment `point`/`climax`, không dày lời | 1.12 |
| `jump-cut-reframe` | Tại ranh giới cut sau hook, xen kẽ 1.0 ↔ 1.12 | che jump cut |
| Không zoom | CTA, sincere, cảnh demo cần toàn khung, khi đang có transition (CR-02) | — |

## Đoạn nào chữ động / highlight
- `keyword-pop`: số + đơn vị ("25 phút"), từ nhấn mạnh trong từ điển, cụm liệt kê ("Mẹo số một"). **Chỉ dùng từ có thật trong transcript.**
- `callout`: segment `proof` có số và dài ≥ 2 s.
- `headline`: hook (Captions hiển thị kiểu headline).
- Thời điểm: lấy từ word timestamp (`timing: "word"`); không có → `segment` + 0.15 s.

## Khi nào KHÔNG dùng hiệu ứng (restraint là một quyết định)
1. Khoảnh khắc chân thành / cảm xúc.
2. Lời nói quá dày (thêm chữ động sẽ khó đọc).
3. CTA — khung hình yên, chỉ caption.
4. Trong cửa sổ transition (CR-02) và trong `minGapBetweenAccentsSec` của accent trước.
5. Khi video gốc đã có chữ cứng (burned-in) ở vùng caption → giảm overlay (cần subject/text box từ analysis).
6. Hết ngân sách 10 s → accent điểm thấp bị bỏ, ghi vào `dropped` với lý do.

## Xây dựng cao trào
- Segment quan trọng nhất trong 60% cuối = `climax`.
- Mật độ accent tăng dần: hook (1 push + 1 pop) → build (thưa) → climax (punch-in + keyword-pop cùng segment = "paired accent") → CTA (yên).
- Intensity `dynamic` tăng mức zoom (1.18) và nới ngân sách, không đổi cấu trúc.

## Tính liên tục giữa các cảnh
- Mức zoom được **giữ** sau mỗi move đến move kế tiếp (Skill 03); không reset vô cớ.
- Xen kẽ mức zoom ở jump cut để hai shot liền nhau khác nhau rõ rệt (≥ 6%).
- Một style caption cho toàn video; chỉ đổi `captionMode`, không đổi font/màu giữa chừng.
- Màu nhấn (accent color) dùng chung cho keyword-pop, callout và highlight.
