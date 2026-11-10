# Conflict rules CR-01 … CR-10 (áp dụng ở stage `conflict-check`)

Thứ tự ưu tiên khi hai quyết định đụng nhau (cao → thấp):

**Toàn vẹn lời nói/âm thanh → Đọc được phụ đề → Không che chủ thể → Hook → Camera → Transition → VFX → SFX**

Mục thấp hơn bị **bỏ** (không "dời đi" tùy tiện) và ghi vào `warnings` của plan revision.

| ID | Quy tắc | Phát hiện bằng | Xử lý |
|---|---|---|---|
| CR-01 | Chỉ một chuyển động camera tại một thời điểm. | `cameraTrack.moves` giao nhau | Giữ move có `priority` cao hơn; move kia bỏ. |
| CR-02 | Không đổi zoom/punch-in trong cửa sổ transition (±`durationSec`/2). | move ∩ transition window | Camera ưu tiên hơn: transition hạ về cut (reframe-step đúng tại cut không tính là xung đột). |
| CR-03 | Bảo vệ hook 0–2s: không transition, không VFX làm giảm độ đọc. | thời gian < `hookEndSec` | Bỏ transition/VFX trong hook. |
| CR-04 | Phụ đề luôn đọc được: blur/glow/flash không áp lên layer caption; camera không di chuyển caption. | layer target = caption | Caption composite **sau** camera và VFX. |
| CR-05 | Ngân sách accent theo 2 kênh: overlay (keyword-pop, callout, headline, VFX accent) ≤ `maxAccentsPer10s`; camera ≤ `maxCameraMovesPer10s`. Một camera + một overlay trong cùng segment = "paired accent". SFX có ngân sách riêng `maxSfxPer10s`. | mọi cửa sổ trượt 10 s + `minGapBetweenAccentsSec` trong kênh | Giữ accent có `score` cao nhất, bỏ phần còn lại (ghi vào `dropped`). |
| CR-06 | Toàn vẹn lời nói: transition chỉ mượn handle **hình** từ đoạn đã cắt; audio giữ điểm cắt (fade 10 ms); không có lời trong nửa giữa cửa sổ transition; không time-stretch giọng. | `transitionPlan` × speech ranges | Hạ về hard cut. |
| CR-07 | SFX chỉ đi kèm một sự kiện hình (transition/pop/callout), thấp hơn giọng ≥ 12 dB khi đè lên lời. | `audioMixPlan.sfx[].anchor` | Bỏ SFX không có anchor; giảm gain. |
| CR-08 | Mỗi section có đúng một owner; skill sau chỉ đọc. | `ownerSkill` | Muốn sửa section khác → tạo `suggestedFix` cho owner. |
| CR-09 | Overlay không che subject box > 15% diện tích; crop camera phải chứa trọn subject box. | `analysis.subjectBoxes` (nếu có) | Caption đổi vị trí theo `placementCandidates`; camera giảm zoom. |
| CR-10 | Tất định & đảo ngược được: cùng input → cùng plan; mọi random có `seed` lưu trong plan; mỗi render ra đường dẫn revision mới. | review plan | Từ chối plan thiếu seed hoặc ghi đè output. |
