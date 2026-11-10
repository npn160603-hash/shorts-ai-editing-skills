# core — hợp đồng dữ liệu dùng chung (không phải Skill)

Mọi Skill dùng chung các hợp đồng này để **không trùng chức năng** và nối được với nhau.

| File | Vai trò |
|---|---|
| `schemas/capability-manifest.schema.json` | Editor **thật sự** làm được gì: `implemented / documented / missing / incompatible` + bằng chứng. Orchestrator chỉ bật tính năng `implemented`. |
| `schemas/skill-registry.schema.json` | Bật/tắt Skill, ai sở hữu section nào, cần capability nào. File thực: `../skills.registry.json`. |
| `schemas/shorts-edit-plan.schema.json` | Envelope có `revision`; mỗi section một owner; `pathTemplate` có `{revision}` (không ghi đè). |
| `schemas/transcript.schema.json` | Transcript + word timestamps; cờ `wordTimestampsReliable`. |
| `lib/sae_schema.py` | Validator JSON Schema (tập con draft 2020-12), chỉ stdlib. |
| `lib/sae_timeline.py` | Timebase source→output, remap từ, frame snap. Mở rộng `docs/02-timeline-contract.md` của V1.1. |
| `lib/sae_text.py` | NFC, grapheme tiếng Việt/emoji, tách từ giữ dấu câu, ước lượng độ rộng. |
| `lib/sae_testutil.py` | Tiện ích test FFmpeg (tự skip khi không có ffmpeg). |
| `lib/sae_asr.py` | Đổi output faster-whisper / openai-whisper / WhisperX / whisper.cpp / SRT / VTT → transcript chuẩn; kiểm tính hợp lý word timestamps (`reliabilityNotes`). |
| `lib/sae_media.py` | ffprobe, phát hiện VFR, lệnh chuẩn hoá CFR ra file mới. |
| `lib/sae_fontmetrics.py` | Đo độ rộng chữ từ file TTF/OTF (stdlib), quy đổi cỡ chữ libass, kiểm glyph thiếu. |
| `lib/sae_layout.py` | Safe zone theo nền tảng, hợp nhất nhiều nền tảng. |
| `lib/sae_easing.py` | Easing dùng chung + biểu thức FFmpeg; có `back-out`. |
| `fonts/` | Be Vietnam Pro Bold/SemiBold (SIL OFL 1.1). |
| `schemas/platform-safe-zones.schema.json`, `schemas/subject-boxes.schema.json` | Safe zone, hộp chủ thể. |
| `examples/asr/` | Mẫu input ASR các định dạng. |
| `references/contracts.md` | Quy ước thời gian, toạ độ, quyền sở hữu, revision. |
| `references/motion-plan-v1_2-proposal.md` | Đề xuất mở rộng ShortsMotionPlan (không sửa V1.1). |

Công cụ tuỳ chọn ngoài core: `../tools/subject_boxes.py` (phát hiện mặt bằng OpenCV).
