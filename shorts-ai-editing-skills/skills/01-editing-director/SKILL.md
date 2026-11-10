---
name: editing-director
description: >-
  Đạo diễn dựng Shorts: phân tích transcript (output time) thành vai trò từng đoạn (hook, point,
  proof, climax, CTA), rồi quyết định đoạn nào cắt chặt, giữ lâu, zoom, chữ động, highlight — và
  đoạn nào cố ý KHÔNG dùng hiệu ứng — trong ngân sách hiệu ứng theo intensity.
---

# Skill 01 — AI Video Editing Director

## 1. Mục đích
Đưa ra **quyết định dựng có lý do** để các skill thực thi (Captions, Camera, Transitions, VFX, Audio) không tự ý thêm hiệu ứng. Director không render gì.

## 2. Khi nào dùng
Mọi lần dựng tự động có hơn một loại nhấn (zoom, chữ, SFX). Chạy sau Skill 04.

## 3. Khi nào không dùng
- Người dùng chỉ muốn phụ đề thường / chỉ cắt khoảng lặng.
- Video không lời (montage nhạc) → cần director theo beat (chưa thuộc phạm vi v1; dùng Skill 07 beat grid + quy tắc riêng).

## 4. Đầu vào
Transcript **output-time** (từ Skill 04, hoặc identity), danh sách điểm cut (output time), intensity + `effectBudget` (Orchestrator), tuỳ chọn: scene changes, subject boxes, `ai_overrides`.

## 5. Đầu ra
- `ContentAnalysis` — `schemas/content-analysis.schema.json`.
- `DirectorDecisions` — `schemas/director-decisions.schema.json`: `segments[]` (pacing, protect, captionMode, restraint) + `accents[]` + `dropped[]` (minh bạch vì sao bị bỏ).

## 6. Quy trình
1. `analyze()`: đặc trưng đo được (wordsPerSec, câu hỏi, số, từ nhấn, chân thành, scene change) → role + importance + keyword (chỉ từ có thật).
2. Chọn climax = đoạn quan trọng nhất trong 60% cuối.
3. `decide()`: sinh ứng viên accent theo `references/decision-rules.md`.
4. Lọc theo ngân sách: hai kênh (overlay, camera), min gap trong kênh, tối đa/10 s, không chồng camera (CR-01).
5. Ghi `restraint` cho đoạn cố ý để yên.

## 7. Công cụ
Python stdlib (`lib/director.py`). LLM local tuỳ chọn (`references/ai-hooks.md`).

## 8. Preset / thuật toán
`BUDGETS` và `PUNCH_LEVELS` theo intensity; từ điển VI/EN (bỏ dấu) cho CTA/proof/point/sincere/emphasis nằm ở `references/lexicon.json` — **sửa theo kênh không cần code** (cụm nhiều chữ được hỗ trợ).

## 9. Phối hợp
- Captions đọc `captionMode` + accents `keyword-pop/headline/callout`.
- Camera đọc accents `smooth-push/punch-in/jump-cut-reframe`.
- Audio đọc accents để gắn SFX (nếu cho phép).
- `protectAfterSec` gửi ngược Skill 04 (tối đa 1 lần chạy lại).

## 10. Nghiệm thu
- `python tests/test_director.py` pass.
- Với transcript mẫu: hook có push + 1 keyword; CTA không có accent; mọi `target` là chuỗi con của transcript; không hai camera move chồng nhau; số accent overlay/10 s ≤ ngân sách.
- Xem preview: không có đoạn nào "nhấn liên tục" > 3 accent trong 4 s ở intensity normal.

## 11. Giới hạn
Heuristic từ khóa không hiểu mỉa mai, ẩn ý; vai trò có thể sai với cấu trúc lạ. Không thấy hình (trừ khi có subject boxes/scene detect).

## 12. Fallback
- Không transcript → không chạy; Orchestrator chỉ cho phép audio + QA.
- Không word timestamps → accent neo đầu segment (`timing: "segment"`).
- Skill tắt → các skill sau chạy chế độ "plain" (caption chuẩn, không zoom, không SFX).
