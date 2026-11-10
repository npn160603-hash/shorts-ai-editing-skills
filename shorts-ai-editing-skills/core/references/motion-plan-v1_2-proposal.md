# Đề xuất mở rộng ShortsMotionPlan → v1.2 (không sửa file V1.1)

Gói này **không chỉnh** `shorts-motion-designer` V1.1. Phần dưới là đề xuất bổ sung (additive) để khi bạn nâng V1.1, các Skill mới dùng được hết; hiện tại `captions.to_motion_plan()` vẫn xuất đúng v1.0.

| Vấn đề ở v1.0 | Đề xuất v1.2 | Tương thích ngược |
|---|---|---|
| Chỉ 4 easing, "pop" không nảy | thêm `"back-out"` (đã có trong `core/lib/sae_easing.py`, đỉnh ≈ 104%) | enum mở rộng; adapter v1.0 gặp `back-out` → dùng `ease-out` |
| `position.y` animation mơ hồ (tuyệt đối hay offset) | `animations[].mode: "absolute" \| "offset"` (mặc định `absolute`) | thiếu field = hành vi cũ |
| Cue phẳng, không có từ | `cues[].words[]` `{text,startSec,endSec}` + `cues[].pageId` | field tuỳ chọn |
| Preset không được tham chiếu | `elements[].presetRef` + `presetParams` (số, đã kẹp) | adapter bỏ qua nếu không hỗ trợ |
| `styles` nhận mọi key | whitelist: fontFamily, fontFile, fontSize(em px), fontWeight, fill, stroke, strokeWidth, maxLines, lineHeight | key lạ → cảnh báo, không render |
| Không có vùng an toàn theo nền tảng | `safeArea.platforms: ["tiktok", ...]` → hợp nhất từ `core/examples/platform-safe-zones.json` | giữ 4 số cũ |
| `parentId` không kiểm vòng | validator: ID duy nhất, không vòng, parent phải là `group` | — |

Đổi `version` thành `"1.2"` khi áp dụng, giữ đọc được `"1.0"`.
