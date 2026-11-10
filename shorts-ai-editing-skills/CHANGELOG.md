# Changelog

## 1.3.0 — 2026-11-11
- **Video dài → nhiều Shorts** (`shorts.py clips`, `orchestrator/lib/highlights.py`): chấm điểm cửa sổ câu (hook, mật độ keyword, nhịp nói, khoảng lặng, phạt mở đầu yếu/CTA), chọn đoạn không chồng nhau, trích chính xác khung hình rồi dựng từng clip; `--llm` chỉ cộng/trừ tối đa ±1 điểm.
- **Kể chuyện từ kịch bản** (`shorts.py story`, `orchestrator/lib/story.py`, `core/lib/sae_tts.py`): TTS local (Piper / Windows SAPI / espeak-ng) hoặc giọng tự thu; mỗi câu một cảnh từ thư viện có giấy phép (`[scene:]`/`[clip:]`), crop 9:16, ghi credits; thiếu cảnh → khung tối, không lấy video người khác.
- **Lớp đồ hoạ** (`orchestrator/lib/overlays.py`): tiêu đề hook, chữ nổi từ khoá, thanh tiến trình, thẻ CTA — vẽ bằng libass chung với phụ đề, bật/tắt từng lớp.
- **Bộ đăng bài** (`orchestrator/lib/publish.py`): tiêu đề/mô tả/hashtag từ lời nói, ảnh bìa từ khung rõ nhất của hook (không dính phụ đề), credits.
- **Hàng loạt** (`shorts.py batch`): transcript cạnh video, bỏ qua video đã xong, `batch-report.csv`.
- Preview 540×960 (nhanh ~4×), bản cuối 1080×1920; **khớp nhấn theo nhịp nhạc** (±0.12 s, chỉ khi BPM đủ tin cậy).
- **LLM local tuỳ chọn** qua Ollama (`core/lib/sae_llm.py`): vai trò câu, chấm đoạn, ý tưởng tiêu đề — mọi kết quả được code kiểm lại.
- `tools/safe_zone_check.py`: vẽ vùng UI từng nền tảng lên một khung hình.
- Phụ đề không vượt quá cuối video (`build_track(duration=...)`).
- CI GitHub Actions: Ubuntu + **Windows**, Python 3.11/3.12, FFmpeg, `check_all.py` + chạy thử `story`.
- 13 test mới (`orchestrator/tests/test_v13.py`).

## 1.2.0 — 2026-11-11
- `tools/trend_research.py`: nghiên cứu Shorts đang nổi qua YouTube Data API (chỉ metadata, không tải video), xếp hạng theo lượt xem/ngày, rút mẫu hình tiêu đề/thời lượng, báo cáo `report.md/.csv`; nhận thêm link Douyin/TikTok tự gom.
- `tools/fetch_stock.py`: tải cảnh minh hoạ từ Pexels/Pixabay (API chính thức), ưu tiên khung dọc ≤1080p, tự ghi credits.
- `scripts/shorts.py`: dựng bằng **một lệnh** (`edit`, `status`, `capabilities`); chạy nền `--detach`; tiến độ `progress.jsonl`; mã thoát rõ ràng; cache transcript; mỗi lần chạy một revision mới.
- Tự phát hiện năng lực máy (`core/lib/sae_env.py`) → manifest có bằng chứng, không cần audit tay khi dùng độc lập.
- Nhận dạng giọng nói local tuỳ chọn bằng faster-whisper (`core/lib/sae_transcribe.py`).
- Tích hợp **OpenCode**: `AGENTS.md`, lệnh `/shorts` và `/shorts-status`, `scripts/install_opencode.py` (không ghi đè, không sửa `opencode.json` có sẵn).
- `sae_asr.load_any` đọc cả transcript định dạng của gói (kiểm lại, chỉ hạ độ tin cậy).

## 1.1.0 — 2026-11-10
- **Runner thật** (`orchestrator/lib/runner.py`): chạy cả chuỗi, render preview, QA, tự sửa theo `suggestedFix` (vòng revise có kiểm "không tiến triển"), export; mỗi vòng một `rev-<n>/` mới + `shorts-edit-plan.json` hợp lệ schema. Backend có thể thay (FFmpeg tham chiếu ↔ pipeline của editor).
- **Conflict-check tập trung** (`orchestrator/lib/conflicts.py`) áp CR-01…CR-10 ở một chỗ, có log.
- **Bộ chuyển transcript** (`core/lib/sae_asr.py`): faster-whisper/openai-whisper, WhisperX, whisper.cpp, SRT/VTT; kiểm tính hợp lý của word timestamps.
- **VFR**: phát hiện & chuẩn hoá CFR không phá file gốc (`core/lib/sae_media.py`).
- **Font thật**: đóng gói Be Vietnam Pro (OFL); đo độ rộng chữ bằng file font (stdlib); quy đổi cỡ chữ cho libass để preview = export; kiểm tra glyph thiếu. Test render xác nhận chữ không tràn safe area.
- **Phát hiện mặt (tuỳ chọn)**: `tools/subject_boxes.py` (OpenCV 4.x, Haar có sẵn hoặc YuNet), remap qua cut list.
- **Safe zone theo nền tảng** (`core/examples/platform-safe-zones.json`, ước lượng — cần đo lại), căn giữa vùng an toàn bất đối xứng.
- **Easing `back-out`** (nảy nhẹ) dùng chung; caption pop có overshoot; đề xuất v1.2 cho ShortsMotionPlan.
- **Từ điển Director** tách ra `references/lexicon.json` (sửa theo kênh, không cần code).
- `scripts/doctor.py`: kiểm tra máy người dùng (FFmpeg, libass, xfade, font, OpenCV, escape đường dẫn Windows).

## 1.0.0 — 2026-11-10
Bản đầu: 8 Skill + Orchestrator + core, runtime tham chiếu, 78 test.
