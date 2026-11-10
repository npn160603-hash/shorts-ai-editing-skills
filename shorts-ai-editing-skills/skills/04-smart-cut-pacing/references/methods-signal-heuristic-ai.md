# Signal vs Heuristic vs AI — phân loại năng lực Skill 04

| Chức năng | Loại | Cần gì | Độ tin cậy | Ghi `method` |
|---|---|---|---|---|
| Silence detection | **Tín hiệu** | FFmpeg `silencedetect` | Cao với giọng sạch; kém khi có nhạc nền | `signal` |
| Pause từ khoảng hở word timestamps | Heuristic trên dữ liệu ASR | word timestamps đáng tin | Trung bình–cao | `heuristic` |
| Scene change | **Tín hiệu** | FFmpeg `select='gt(scene,0.35)',showinfo` | Tốt với cắt cứng, kém với fade | `signal` |
| Filler token (ừm, à, uh) | Heuristic | transcript + từ điển đóng | Trung bình | `heuristic` |
| Retake (nói lại câu) | Heuristic | transcript segments | Thấp–trung bình → QA xem | `heuristic` |
| Jump cut timing | Heuristic | cut list + preset | Cao | — |
| Speech-aware timing (giữ hơi thở) | Heuristic | `keepPauseSec` | Cao | — |
| Rhythm-based editing theo nhạc | Tín hiệu + heuristic | beat grid (Skill 07) | Phụ thuộc beat detect | `signal` |
| Semantic cut (lặp ý, lan man, lạc đề) | **Cần AI** | LLM local đọc transcript | Phụ thuộc model | `ai` |
| Phát hiện câu "quan trọng phải giữ" | **Cần AI** hoặc người dùng | LLM / đánh dấu tay | — | `ai` / `manual` |

Nguyên tắc: kết quả `ai` **không** được bỏ qua ngân sách `maxRemovedRatio` và luôn hiển thị trong báo cáo để người dùng hoàn tác từng mục.

## Prompt gợi ý cho LLM local (semantic cut)
Đầu vào: danh sách segment `{id, text, startSec, endSec}`. Yêu cầu trả **JSON thuần**:
`[{"segmentId": "...", "reason": "semantic", "why": "lặp lại ý của s3"}]` — chỉ đề xuất segment trọn vẹn, không cắt giữa câu. Code sẽ đổi thành removal `method:"ai"`, `confidence` tối đa 0.7.
