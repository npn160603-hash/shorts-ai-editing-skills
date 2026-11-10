---
name: smart-cut-pacing
description: >-
  Cắt khoảng lặng, từ đệm (ừm/à/uh), câu nói lại (retake) và đầu/đuôi thừa để tạo jump cut có nhịp
  cho Shorts; xuất CutList ở source time và remap transcript sang output time. Phân biệt rõ phần
  đo tín hiệu, phần heuristic và phần cần AI.
---

# Skill 04 — Smart Cut & Pacing

## 1. Mục đích
Rút gọn video nói chuyện thành nhịp Shorts mà **không làm méo lời nói**: bỏ khoảng lặng dài, filler, retake, đầu/đuôi chết. Đây là **skill duy nhất được đổi timebase** (source → output).

## 2. Khi nào dùng
- Talking-head, podcast clip, hướng dẫn nói; người dùng yêu cầu "cắt đoạn thừa / bỏ khoảng lặng / jump cut".
- Trước Director, Captions, Camera, Transitions, Audio (các skill đó cần output time).

## 3. Khi nào không dùng
- Video nhạc/montage mà nhịp do nhạc quyết định (khoảng lặng là chủ ý) → chỉ trim đầu/đuôi.
- Clip đã được người dùng cắt tay (có cờ `userEdited`) → chỉ đề xuất, không áp.
- Khoảng lặng mang cảm xúc (sau câu hỏi tu từ, punchline) — Director đánh dấu `protected` để giữ.

## 4. Đầu vào
- Transcript (`core/schemas/transcript.schema.json`, timebase `source`).
- Tuỳ chọn: log `silencedetect`, log scene detect, danh sách removal `method:"ai"` từ LLM.
- `intensity`, `maxRemovedRatio`, `protected` ranges.

## 5. Đầu ra
- `CutList` — `schemas/cut-list.schema.json` (`segments` giữ lại + `removed` có `reason/method/confidence` + `rejected`).
- Transcript output-time (`remap_transcript`).
- Filter FFmpeg trim/concat (`ffmpeg_concat_filter`) cho editor dùng FFmpeg.

## 6. Quy trình
1. Đo khoảng lặng: `ffmpeg -hide_banner -i in.mp4 -af silencedetect=noise=-35dB:d=0.25 -f null -` → `parse_silencedetect`. Không có → khoảng hở giữa word timestamps (chỉ khi `wordTimestampsReliable`).
2. Biến khoảng lặng thành removal theo preset: giữ `keepPauseSec` mỗi bên để lời không bị "dính".
3. Filler: chỉ token đơn trong danh sách đóng (`FILLERS`). Cụm ("kiểu như") chỉ báo cáo.
4. Retake: hai đoạn liền nhau có 6 từ đầu giống ≥ 72% → bỏ đoạn trước (confidence 0.6, QA phải xem).
5. Removal `method:"ai"` (nếu có) được nhận nhưng vẫn qua cùng ngân sách.
6. Snap frame; ưu tiên removal confidence cao; vượt `maxRemovedRatio` → đẩy vào `rejected`.
7. Sliver < `minKeepSec`: không có lời → cắt luôn; có lời → giữ lại.
8. Remap transcript; xuất filter concat có fade audio 10 ms mỗi mảnh (chống tiếng click).

## 7. Công cụ
FFmpeg (silencedetect, trim/atrim, concat, afade) — đã có trong hầu hết editor. Python stdlib. Không model.

## 8. Preset / thuật toán
| intensity | minSilenceSec | keepPauseSec | minKeepSec |
|---|---|---|---|
| subtle | 0.70 | 0.22 | 0.30 |
| normal | 0.45 | 0.14 | 0.25 |
| dynamic | 0.28 | 0.08 | 0.20 |

Chi tiết phân loại: `references/methods-signal-heuristic-ai.md`; nhịp: `references/pacing-rules.md`.

## 9. Phối hợp
- Trước mọi skill khác. Director có thể trả `protected` ranges → chạy lại skill này 1 lần.
- Danh sách ranh giới cut là input của Skill 05 (transition) và Skill 07 (crossfade audio).
- Camera (Skill 03) dùng ranh giới cut để xen kẽ mức zoom che jump cut.

## 10. Nghiệm thu
- `python tests/test_pacing.py` pass (gồm smoke test FFmpeg thật nếu máy có ffmpeg).
- Trên video thật: không mất âm tiết đầu/cuối câu (nghe 3 ranh giới cut ngẫu nhiên), không click, A/V lệch ≤ 1 frame, `removedRatio ≤ maxRemovedRatio`.
- Không có từ nào trong transcript output nằm trong vùng đã cắt.

## 11. Giới hạn
- `silencedetect` dựa ngưỡng dB: nhạc nền/tiếng ồn làm sai → hạ `noise` hoặc chạy trên track giọng tách riêng.
- Retake/filler là heuristic; không hiểu ngữ nghĩa ("à" có thể là từ có nghĩa).
- Semantic cut (bỏ câu lặp ý, lan man) **cần LLM** — skill chỉ nhận kết quả, không tự làm.
- Không đổi tốc độ lời nói.

## 12. Fallback
- Không silencedetect, không word timestamps → chỉ trim đầu/đuôi theo segment transcript.
- Removal vượt ngân sách → giữ phần confidence cao, phần còn lại vào `rejected` để người dùng xem.
- Skill tắt → CutList identity (1 segment = toàn video); mọi skill sau vẫn chạy với output = source.
