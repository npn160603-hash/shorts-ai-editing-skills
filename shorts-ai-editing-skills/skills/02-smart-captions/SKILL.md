---
name: smart-captions
description: >-
  Phụ đề động chuyên nghiệp cho Shorts (VI/EN): chia trang thông minh không tách từ ghép/số+đơn vị,
  highlight từng từ khi có word timestamp đáng tin, tô keyword từ Director, animation theo ngữ nghĩa,
  preset typography, tránh che mặt khi có subject box; xuất CaptionTrack, file ASS (FFmpeg/libass)
  và ShortsMotionPlan v1.0.
---

# Skill 02 — Smart Dynamic Captions

## 1. Mục đích
Phụ đề **dễ đọc trên điện thoại, khớp lời, có nhấn** — mở rộng phần caption của Shorts Motion Designer V1.1 (không thay thế: vẫn xuất `ShortsMotionPlan` để adapter V1.1 render).

## 2. Khi nào dùng
Video có lời nói và transcript. Người dùng yêu cầu phụ đề/chữ động/karaoke.

## 3. Khi nào không dùng
- Video đã có phụ đề cứng (burned-in) → chỉ xuất `.srt` cho nền tảng, không vẽ thêm.
- Không có transcript (hoặc ngôn ngữ không có font) → bỏ qua, báo cáo.
- Nhạc có lời của bên thứ ba → không chép lời bài hát lên màn hình.

## 4. Đầu vào
Transcript output-time; `DirectorDecisions` (captionMode, keyword-pop); preset (`examples/caption-style-presets.json`); `video` + `safeArea`; tuỳ chọn subject boxes `{startSec,endSec,box:{x,y,w,h}}` (normalized).

## 5. Đầu ra
- `CaptionTrack` — `schemas/caption-track.schema.json` (trang, dòng, từ, placement, animation, CPS, warnings).
- `.ass` có highlight từng từ — `to_ass()` → `ffmpeg -vf "subtitles=captions.ass:fontsdir=fonts"`.
- `ShortsMotionPlan` v1.0 (theo cụm + keyword callout) — `to_motion_plan()`; hợp lệ với schema V1.1.

## 6. Quy trình
1. Chọn chế độ: `word-highlight` chỉ khi `wordTimestampsReliable`; ngược lại `phrase` (`timing: estimated-phrase`, **không** highlight theo từ).
2. Chia khối cứng: hết câu, nghỉ > 0.35 s, đổi captionMode.
3. Chia trang bằng quy hoạch động (`partition`): ít trang, cân đối, phạt tách từ ghép/số+đơn vị/trang 1 từ; giới hạn từ/trang, giây/trang, độ rộng dòng.
4. Ngắt dòng cân bằng (`balance_lines`), tối đa `maxLines`.
5. Nhấn: từ trùng keyword Director → `keyword`; số → `number`.
6. Animation theo `references/emotion-style-map.md`.
7. Vị trí: thử `placementCandidatesY`; bỏ vị trí che subject box > 15% (CR-09); giữ trong safe area **hợp nhất của các nền tảng đích** (`core/examples/platform-safe-zones.json`, căn giữa vùng an toàn bất đối xứng). Pop/hook-reveal có overshoot nhẹ (105% → 100%).
8. Tính CPS, cảnh báo nếu vượt `maxCps`.
9. Xuất ASS / MotionPlan / CaptionTrack cho adapter native.

## 7. Công cụ
Python stdlib. Render: FFmpeg có **libass** hoặc renderer overlay sẵn có của editor. Font **đóng gói kèm**: Be Vietnam Pro (OFL) ở `core/fonts/` — độ rộng chữ được đo bằng chính file font (`core/lib/sae_fontmetrics.py`), cỡ chữ quy đổi cho libass (`fontSize` trong preset = cỡ em kiểu CSS) để preview và export giống nhau; `fontCheck.missingGlyphs` báo ký tự thiếu glyph. Burn bằng `ffmpeg_subtitles_filter(ass, fonts_dir=core/fonts)` (đã escape đường dẫn Windows).

## 8. Preset
`clean-bold` (mặc định), `punchy-3` (1–3 từ/trang, dynamic), `boxed-calm` (hộp nền, đoạn chân thành/hướng dẫn). Thêm preset = thêm object JSON hợp lệ schema, không code.

## 9. Phối hợp
- Đọc Director; không tự chọn keyword ngoài transcript.
- Caption composite **trên cùng**, sau Camera/VFX (CR-04) — camera không làm caption rung.
- Keyword-pop của Director có thể render thành callout (`to_motion_plan(keyword_callouts=...)`) **hoặc** chỉ tô màu trong caption — không làm cả hai cùng chỗ nếu style `punchy-3`.
- Audio (Skill 07) có thể gắn SFX "pop" vào keyword-pop đã nhận.

## 10. Nghiệm thu
- `python tests/test_captions.py` pass (gồm burn ASS thật; test đo pixel xác nhận mọi dòng nằm trong safe area với font đóng gói).
- Không từ nào của caption nằm ngoài transcript; không từ ghép/số+đơn vị bị tách (trừ khi một từ dài hơn cả dòng).
- Frame review: chữ không chạm mép safe area, không che mặt khi có box, dấu tiếng Việt đủ, highlight đổi đúng lúc từ được nói (lệch ≤ 2 frame trên 3 điểm kiểm).

## 11. Giới hạn
- Đo chữ bằng advance width của font, chưa tính kerning/shaping (sai lệch ~1–3%, đã chừa 3%). Font không có file → quay về ước lượng và cảnh báo.
- ASS/libass không có easing tuỳ ý (chỉ `\t` với accel); motion phức tạp hơn cần renderer overlay riêng.
- Danh sách từ ghép là heuristic, chưa phải tách từ tiếng Việt đầy đủ (có thể thay bằng tokenizer như underthesea nếu chấp nhận dependency).

## 12. Fallback
- Không word timestamps → phrase mode.
- Không libass → `to_motion_plan()` + adapter overlay V1.1; tệ nhất: `drawtext` theo trang (không highlight).
- Không subject boxes → vị trí mặc định trong safe area.
- Skill tắt → caption cũ của editor giữ nguyên.
