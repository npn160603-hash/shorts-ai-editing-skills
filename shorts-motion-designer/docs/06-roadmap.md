# 06 — Roadmap ưu tiên theo giá trị

## M0 — Audit & decision

Chọn adapter, baseline, tài liệu compatibility, check source thật. Đây là điều kiện bắt buộc.

## M1 — Caption + hook + 2 presets (nên triển khai trước)

- Caption highlight theo word timestamp.
- Hook reveal, soft-slide/scale-pop.
- Lower-third/card đơn giản.
- Motion switch ON/OFF, test A/B.

## M2 — Preset library & AI Director

- JSON preset whitelist, intensity, per-project style guide.
- Scene-aware placement; avoid face and UI hotspots nếu có detector/boxes.
- Tự nhận biết transcript structure và chọn effect theo trọng tâm (khi có mô hình/heuristic thật).
- QA visual và quality gates tự động ở phạm vi khả thi.

## M3 — Nhóm layer + typography mở rộng

- Parent/child hierarchy, transform/order, deterministic composition.
- Stagger per word/grapheme, safe text layout, multilingual tests.
- Nâng cấp preview/live editor nếu cần.

## M4 — VFX/Camera (chỉ khi có nhu cầu và hỗ trợ thật)

- Mask reveal, glow, 2.5D/parallax, motion blur, transition.
- Cân nhắc chi phí render và lộ trình rollback trước khi thêm hiệu ứng.

**Không triển khai tất cả một lần**. Nâng cấp theo bottleneck thực tế của video Shorts và render performance.
