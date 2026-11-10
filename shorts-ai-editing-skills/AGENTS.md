# AGENTS.md — dựng YouTube Shorts / TikTok / Reels bằng shorts-ai-editing-skills

Dành cho agent (OpenCode, Codex, Claude Code…) khi người dùng nhờ **dựng/edit một video ngắn**.
`PKG` = thư mục chứa file này (thường `.opencode/skills/shorts-ai-editing-skills`).

## Quy tắc bắt buộc
1. **Luôn dựng bằng lệnh có sẵn**, không tự viết pipeline FFmpeg mới:
   `python PKG/scripts/shorts.py edit "<video>" --instruction "<yêu cầu của người dùng, nguyên văn>" [tuỳ chọn]`
2. **Không bao giờ ghi đè hay xoá file của người dùng.** Kết quả nằm ở `<thư mục video>/<tên>_shorts/ai-edit/rev-<n>/`.
3. **Không cài thư viện** (faster-whisper, opencv-python-headless) khi người dùng chưa đồng ý. Hỏi một câu ngắn kèm dung lượng (faster-whisper + model `small` ≈ vài trăm MB).
4. **Nhạc/SFX chỉ dùng file người dùng đưa** và khi họ xác nhận license (`own`/`CC0`/`licensed`). Không tự tải nhạc.
5. Không tự bịa transcript, keyword, hay số liệu đánh giá.

## Quy trình
1. Kiểm tra máy (lần đầu): `python PKG/scripts/doctor.py`. Có dòng FAIL → báo người dùng cách sửa, dừng.
2. Transcript:
   - Có sẵn file `.json`/`.srt`/`.vtt` → `--transcript <file>`.
   - Không có → nếu `faster-whisper` đã cài thì để mặc định `--asr auto` (thêm `--asr-model medium` nếu máy khoẻ); chưa cài → hỏi người dùng cho cài hoặc đưa file phụ đề.
3. Chuyển yêu cầu người dùng thành tham số (chỉ khi họ nói rõ):
   | Người dùng nói | Thêm |
   |---|---|
   | nhẹ nhàng / tối giản | `--intensity subtle` |
   | sôi động / mạnh | `--intensity dynamic --caption-style punchy-3` |
   | chỉ đăng TikTok | `--platforms tiktok` |
   | có nhạc nền (đưa file + license) | `--music f.wav --music-license own --music-proof "..."` |
   | có SFX (đưa thư viện) | `--sfx-library lib.json` |
   | né mặt người (đã cài OpenCV 4.x) | `--detect-faces` |
   | hiệu ứng điện ảnh / glow | `--vfx` |
   | không rung máy / không zoom | `--forbid camera-shake` / `--forbid camera-shake,zoom` |
4. Video > 30 s hoặc máy chậm → chạy nền: thêm `--detach`, rồi hỏi tiến độ bằng
   `python PKG/scripts/shorts.py status "<thư mục _shorts>"` mỗi 20–30 s (đừng chờ một lệnh quá lâu).
5. Đọc kết quả: `run-report.json` (đường dẫn in ở cuối hoặc trong `status`):
   - `final.path` — video xuất. `final.gate` = `pass`/`fail`.
   - `needsHuman` — lỗi không tự sửa được → kể lại cho người dùng bằng lời dễ hiểu.
   - `revisions[].fixesApplied` — các lần tự sửa.
6. Nếu model của bạn xem được ảnh: mở `rev-<n>/contact_sheet.png` và nhận xét ngắn (chữ đọc rõ? che mặt? khung trống?). Không chấm điểm cảm tính.
7. Trả lời người dùng: đường dẫn video, 2–4 dòng về những gì đã làm (cắt bao nhiêu giây, phụ đề kiểu gì, số lần tự sửa), lỗi còn lại nếu có, và một gợi ý chỉnh tiếp.

## Nghiên cứu chủ đề & nguồn cảnh
- Chủ đề đang nổi / cách người khác làm: `python PKG/tools/trend_research.py search --query "<chủ đề>" --region VN --days 7`
  (hoặc `trending --region VN`). Cần `YOUTUBE_API_KEY` (miễn phí). Chỉ đọc metadata công khai → `research/.../report.md`;
  **không tải video của người khác**. Link Douyin/TikTok người dùng tự gom: `--extra-links links.txt`.
- Cảnh minh hoạ có giấy phép: `python PKG/tools/fetch_stock.py --query "<cảnh>" --per-source 5 --out <thư mục>`
  (cần `PEXELS_API_KEY` / `PIXABAY_API_KEY`, miễn phí; tự ghi `credits.csv`).

## Chế độ khác (v1.3)
| Người dùng muốn | Lệnh |
|---|---|
| cắt video dài thành nhiều Shorts | `python PKG/scripts/shorts.py clips "<video>" --count 5 [--min-sec 20 --max-sec 60]` → `clips-report.json` |
| làm video từ kịch bản / kể chuyện | `python PKG/scripts/shorts.py story <kịch bản.txt> --tts sapi\|piper\|espeak [--tts-voice ..] --library <thư mục cảnh>` hoặc `--voice <file thu âm>` |
| dựng cả thư mục | `python PKG/scripts/shorts.py batch "<thư mục>"` (transcript cạnh video; `--redo` để làm lại) |
| tiêu đề lớn đầu video / thẻ kêu gọi cuối | `--hook-title "<chữ>"` / `--cta "<chữ người dùng đưa>"` (không tự bịa CTA) |
| tắt thanh tiến trình / chữ nổi từ khoá | `--no-progress-bar` / `--no-callouts` |
| dùng AI local (đã cài Ollama) | `--llm <model>` — chỉ khi người dùng đồng ý |
- Kết quả có thêm `publish/publish.md` (tiêu đề, mô tả, hashtag, ảnh bìa): đọc và đưa cho người dùng, nói rõ là **gợi ý**.
- Kể chuyện: cảnh chỉ lấy từ `--library` (thư mục của người dùng hoặc từ `fetch_stock.py`) hoặc `--fetch` (Pexels/Pixabay, cần key). Thiếu cảnh → khung tối, báo người dùng; không dùng video của người khác. Luôn đưa `credits.txt`.
- Kiểm chữ có bị UI che không: `python PKG/tools/safe_zone_check.py "<final.mp4>" --at <giây>`.

## Chỉnh lần sau
Chạy lại cùng lệnh với tham số mới → tạo `rev-<n+1>` (transcript được cache, không nhận dạng lại). Muốn nhận dạng lại: `--re-asr`.

## Mã thoát
`0` xong & QA đạt · `3` xong nhưng còn lỗi (xem `needsHuman`) · `2` thiếu đầu vào/cài đặt · `1` lỗi chương trình (gửi `shorts.log` + `progress.jsonl`).

## Khi cần sâu hơn
`PKG/orchestrator/SKILL.md` (điều phối), `PKG/skills/*/SKILL.md` (từng kỹ năng), `PKG/00-ASSESSMENT.md`. Muốn đổi quy tắc nhấn mạnh theo kênh: sửa `PKG/skills/01-editing-director/references/lexicon.json`.
