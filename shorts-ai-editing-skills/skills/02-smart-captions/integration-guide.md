# Tích hợp Skill 02

## Đường A — editor dùng FFmpeg
1. Kiểm tra libass: `ffmpeg -hide_banner -filters | findstr subtitles` (Windows) → có thì `overlay.assSubtitles = implemented`.
2. Ghi `captions.ass` vào `ai-edit/rev-<n>/`, burn: `-vf "subtitles=<ass>:fontsdir=<thư mục font dự án>"`. Trên Windows escape `:` trong đường dẫn (`C\\:/...`).
3. Dùng font đóng gói `core/fonts/` (hoặc chép vào thư mục dự án) và truyền `fontsdir` — preview (CSS `@font-face` cùng file) và export dùng cùng một font; `fontSize` preset là cỡ em CSS, `to_ass()` tự quy đổi.
4. Chọn nền tảng đích (`platforms`) để lấy safe zone; đo lại safe zone bằng ảnh chụp màn hình thật và sửa `core/examples/platform-safe-zones.json`.

## Đường B — editor có renderer overlay (Remotion/Canvas/V1.1 adapter)
- Đọc trực tiếp `CaptionTrack`: mỗi page → một nhóm text; mỗi word là span; active word = `startSec ≤ t < next.startSec`.
- Đo lại chữ bằng font thật; nếu dòng tràn → giảm `fontScale` từng bước 5% (tối thiểu 0.8) rồi mới xuống dòng.
- Hoặc dùng `to_motion_plan()` nếu adapter V1.1 đã có (mất highlight theo từ).

## Toggle / rollback
- `smart-captions.enabled=false` → giữ caption cũ của editor.
- Preset người dùng chọn lưu trong project settings; không ghi đè preset gốc.

## Kiểm thử trên editor
Clip 12–20 s tiếng Việt có số và từ ghép; render; trích frame tại 3 thời điểm bắt đầu từ được nhấn; kiểm highlight & dấu.
