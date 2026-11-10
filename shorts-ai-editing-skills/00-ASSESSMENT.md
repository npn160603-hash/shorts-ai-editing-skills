# 00 — Đánh giá, khoảng trống, xếp hạng, kiến trúc và lộ trình

> Phạm vi: đã đọc toàn bộ 17 file của **Shorts Motion Designer — Standalone V1.1** trong `E:\Tool Edit Video Short\Shorts-Motion-Designer-Standalone-v1.1\shorts-motion-designer`. **Chưa** có source code của editor Shorts → mọi đánh giá "đã chạy" dưới đây là chạy **trong gói này** (Python stdlib + FFmpeg 6.1.1 trên máy thử), **không** phải trong editor của bạn.

---

## 1. Đánh giá bộ kỹ năng hiện tại (V1.1)

### Điểm mạnh (giữ nguyên, tái sử dụng)
- Trung thực về phạm vi: nói rõ là tài liệu + schema, không phải renderer (`README.md`, `SKILL.md`).
- Hợp đồng timeline tốt: giây float, `[start,end)`, map sang output time sau cut, chống drift, VFR (`docs/02-timeline-contract.md`).
- Ý thức Unicode/tiếng Việt: grapheme, NFC/NFD, font fallback.
- Kiến trúc tách tầng Director → Plan → Adapter → Renderer → QA (`docs/04-implementation-paths.md`) — gói mới đi đúng hướng này.
- Quy tắc an toàn: không ghi đè, không reset/clean, không API trả phí, không tuyên bố tích hợp khi chưa render.

### Điểm yếu / lỗi cụ thể tìm thấy khi kiểm tra
| # | Vấn đề | Bằng chứng | Hệ quả |
|---|---|---|---|
| 1 | Không có mã thực thi nào ngoài `scripts/check_package.py`; script này **không validate JSON theo schema** (chỉ kiểm version, khoảng thời gian, safe area). | `scripts/check_package.py` | Ví dụ sai schema vẫn "PASS". |
| 2 | Schema chỉ mô tả **overlay** (`text/rectangle/ellipse/group`). Không biểu diễn được cut/time-remap, chuyển động video nền (camera), transition, audio. | `schemas/shorts-motion-plan.schema.json` | 4/8 Skill mới không thể nằm trong plan V1.1. |
| 3 | Ngữ nghĩa animation `position.y` mơ hồ: element đặt `y=0.74` nhưng animation `from 0.78 → 0.74` — tuyệt đối hay offset? | `examples/shorts-motion-plan.example.json` (`caption-text`) | Mỗi adapter có thể hiểu khác nhau. |
| 4 | Cue phụ đề phẳng, không có mảng từ/trang → không biểu diễn được "highlight từ đang nói" theo trang 1–2 dòng. | `cues[]` chỉ có `text` + `source` | Word-highlight phải sống ngoài plan. |
| 5 | `styles` nhận mọi key (`additionalProperties` bất kỳ), không có `stroke`, `maxLines`, font fallback. | schema `elements[].styles` | Adapter phải tự whitelist; dễ lệch preview/export. |
| 6 | Preset library không được plan tham chiếu (không có `presetRef`), đánh dấu `PROPOSAL_NOT_ENGINE_READY`, không có keyframe; chỉ 4 easing, không có overshoot/back cho "pop". | `examples/preset-library.example.json` | Preset là ý tưởng, chưa dùng được. |
| 7 | `parentId` có trong schema nhưng không kiểm vòng lặp/không có transform group. | schema | Nested group chưa an toàn. |
| 8 | Không có cách máy-đọc-được để phân loại *đã triển khai / có tài liệu / thiếu / không tương thích*. | — | Orchestrator không thể "kiểm tra khả năng thực tế". |
| 9 | Chỉ có một cờ `motionEnabled` toàn cục; không bật/tắt từng nhóm. | `SKILL.md` P1 | Không rollback từng phần. |
| 10 | Không có gì về âm thanh (loudness, ducking, SFX, license) và không có quy tắc tốc độ đọc (CPS). | toàn gói | Hai lỗi phổ biến nhất của Shorts tự động không được kiểm. |

**Kết luận:** V1.1 là nền tảng **kiến thức + hợp đồng overlay** tốt; thiếu runtime tham chiếu, thiếu mô hình cho các tầng ngoài overlay, thiếu manifest năng lực và registry bật/tắt. Gói mới **không sửa** V1.1 (giữ tương thích), mà xây quanh nó và biên dịch phụ đề về đúng `ShortsMotionPlan v1.0` (đã kiểm hợp lệ với schema V1.1).

### Phân loại năng lực sau khi có gói mới (theo đúng 4 nhóm bạn yêu cầu)
"Có runtime tham chiếu" = có code + test chạy thật với FFmpeg 6.1.1 trong gói; **vẫn phải tích hợp vào editor** mới thành "đã triển khai thực tế".

| Năng lực | Trạng thái |
|---|---|
| Silence/filler/retake cut, remap transcript, concat frame-exact | Có runtime tham chiếu (Skill 04) |
| Director quyết định accent/restraint theo ngân sách | Có runtime tham chiếu (Skill 01, heuristic) |
| Phụ đề trang thông minh VI/EN, highlight từng từ, ASS, tránh mặt | Có runtime tham chiếu (Skill 02) |
| Zoom/punch-in/reframe/shake có kiểm soát (FFmpeg) | Có runtime tham chiếu (Skill 03) |
| Transition xfade không đổi thời lượng (handle) | Có runtime tham chiếu (Skill 05) |
| Color/vignette/glow/blur/motion-blur (FFmpeg) | Có runtime tham chiếu (Skill 06, opt-in) |
| Loudness 2 lượt, ducking tất định, SFX có license, BPM | Có runtime tham chiếu (Skill 07) |
| QA tự động + contact sheet | Có runtime tham chiếu (Skill 08) |
| Runner thực thi + conflict-check tập trung + vòng tự sửa theo QA | Có runtime tham chiếu (v1.1, `orchestrator/lib/runner.py`) |
| Đọc transcript Whisper/whisper.cpp/WhisperX/SRT/VTT; xử lý video VFR | Có runtime tham chiếu (v1.1, `core/lib/sae_asr.py`, `sae_media.py`) |
| Đo chữ bằng font thật, font tiếng Việt đóng gói, preview = export | Có runtime tham chiếu (v1.1) |
| Subject boxes (mặt) | Có runtime **tuỳ chọn** (OpenCV 4.x, `tools/subject_boxes.py`) |
| Light sweep, mask reveal, nested group, character stagger | **Chỉ tài liệu** (cần overlay renderer của editor) |
| Semantic cut, vai trò câu bằng LLM, VLM review | **Thiếu** — cần model local (xem §5) |
| 2.5D parallax, motion-match transition, tách giọng khỏi nhạc | **Thiếu** — cần model/CV chuyên sâu |
| Subpixel camera trên FFmpeg thuần | **Không tương thích** (crop pixel nguyên) → dùng Remotion/Canvas nếu cần |

---

## 2. Năng lực còn thiếu để tạo Shorts chất lượng cao
1. **Cắt nhịp** (khoảng lặng, filler, retake) có remap transcript — nền của mọi thứ khác.
2. **Quyết định dựng có lý do và có ngân sách** (đoạn nào nhấn, đoạn nào để yên).
3. **Phụ đề trang hoá** cho điện thoại: ngắt dòng không tách từ ghép tiếng Việt / số+đơn vị, CPS, tránh mặt.
4. **Camera ảo** che jump cut và nhấn ý (punch-in xen kẽ).
5. **Âm thanh**: loudness chuẩn nền tảng, fade chống click, ducking, SFX/nhạc có license.
6. **QA dựa bằng chứng** + vòng sửa tự động.
7. **Manifest năng lực + registry bật/tắt + revision** để điều phối và rollback.
8. (Sau) Phát hiện chủ thể, semantic editing, VFX overlay nâng cao.

---

## 3. Xếp hạng Skill mới

Điểm ưu tiên = Giá trị × 2 − Độ khó − Chi phí xử lý (thang 1–5).

| Hạng | Skill | Giá trị | Độ khó | Chi phí xử lý | Điểm | Ghi chú |
|---|---|---|---|---|---|---|
| 1 | 04 Smart Cut & Pacing | 5 | 2 | 1 | 7 | Một lần `silencedetect` + concat. Lợi ích lớn nhất cho talking-head. |
| 2 | 02 Smart Dynamic Captions | 5 | 3 | 1 | 6 | 80% người xem Shorts tắt tiếng; ASS/libass rẻ. |
| 3 | 07 Audio Director | 4 | 2 | 1 | 5 | loudnorm 2 lượt + fade = chênh lệch "nghiệp dư/chuyên nghiệp". |
| 4 | 08 Visual Quality Reviewer | 4 | 2 | 1 | 5 | Chặn lỗi trước khi xuất; nuôi vòng revise. |
| 5 | Orchestrator (+ core) | 4 | 3 | 1 | 4 | Bắt buộc để các Skill phối hợp; rẻ khi chạy. |
| 6 | 01 Editing Director | 4 | 3 | 1 | 4 | Heuristic rẻ; LLM tuỳ chọn tăng chất lượng. |
| 7 | 03 Camera Movement | 4 | 3 | 2 | 3 | Re-encode toàn video; cần subject boxes để tốt nhất. |
| 8 | 05 Advanced Transitions | 2 | 3 | 2 | -1 | Shorts nói chuyện chủ yếu là cut; giá trị thấp nếu lạm dụng. |
| 9 | 06 Cinematic VFX | 2 | 3 | 4 | -3 | Đắt render, dễ phản tác dụng → opt-in, làm cuối. |

## 4. Skill triển khai được **không cần AI model**
- **04** (silencedetect, scene score, filler/retake heuristic), **02** (paging DP, ASS, placement theo box nếu có), **03** (FFmpeg scale+crop, center-weighted), **05** (xfade + handle), **06** (filter FFmpeg), **07** (loudnorm, volume envelope, amix, BPM bằng tự tương quan), **08** (ffprobe/blackdetect/freezedetect/silencedetect + quy tắc), **01** (heuristic từ khóa + đặc trưng đo được), **Orchestrator** (parser từ khóa VI/EN).
- Điều kiện duy nhất: **transcript có word timestamps** — thường editor đã có ASR (nếu chưa: xem §5).

## 5. Phần **cần mô hình AI / xử lý chuyên sâu** (tất cả có thể chạy local, miễn phí — kiểm license từng model trước khi dùng)
| Nhu cầu | Skill hưởng lợi | Hướng local gợi ý |
|---|---|---|
| Word timestamps tin cậy | 02, 04, 01 | Whisper chạy local (ví dụ faster-whisper, giấy phép MIT) với `word_timestamps`. |
| Phát hiện mặt/người (subject boxes) | 02, 03, 08 | OpenCV (Apache-2.0) với detector mặt nhẹ; hoặc MediaPipe (Apache-2.0). Chạy 2–5 fps rồi nội suy. |
| Semantic cut, vai trò câu, keyword ngữ nghĩa | 04, 01 | LLM local qua llama.cpp/Ollama (MIT); bắt buộc trả JSON theo schema, code kiểm lại (keyword phải có thật, removal `method:"ai"` qua ngân sách). |
| Review hình bằng VLM | 08 | VLM local đọc contact sheet; chỉ thêm finding `source: vision-model`, không chấm điểm. |
| Tách giọng khỏi nhạc có sẵn | 07 | Model source separation (ví dụ Demucs, MIT) — nặng, chỉ khi cần. |
| Denoise bằng model | 07 | `arnndn` của FFmpeg + model RNNoise (BSD). |
| 2.5D parallax, motion-match, mask chủ thể | 03, 05, 06 | Segmentation/depth model — để giai đoạn cuối. |

## 6. Kiến trúc phối hợp (không trùng chức năng)

```
EditRequest ──► Orchestrator ◄── CapabilityManifest (implemented/documented/missing/incompatible)
                    │            ◄── skills.registry.json (enabled, owns, requires)
                    ▼
probe → transcript → [04 Cut] → transcript@output → [01 Director]
                                   ├─► [02 Captions] ─┐
                                   ├─► [03 Camera] ───┼─► [05 Transitions] → [06 VFX] → [07 Audio]
                                   │                  │
                                   └──────────────────┴─► Shorts Motion Designer V1.1 (motionPlan, overlay)
                    → conflict-check (CR-01…10) → preview → [08 QA] → revise ≤ N → export rev-<n>
```

Quy tắc chống trùng:
- **Một section — một owner** (`core/references/contracts.md`). Skill khác chỉ đọc; muốn đổi thì gửi `suggestedFix`.
- Cắt khoảng lặng chỉ ở 04 (07 không cắt). Fade chống click nằm trong trim của 04/05.
- Overlay/motion preset vẫn thuộc **V1.1**; 02 biên dịch về `ShortsMotionPlan v1.0` thay vì tạo engine overlay mới. Hook-reveal, soft-slide-up, scale-pop… dùng lại tên preset V1.1.
- Nhóm F "Short-form Creative Editing" của V1.1 được **hiện thực hoá** thành Skill 01; nhóm G "Editing QC" thành Skill 08 (thêm quy tắc mới, giữ checklist cũ).
- Nhóm H "Integration Architecture" được hiện thực hoá thành Capability Manifest + registry.

## 7. Lộ trình triển khai theo giai đoạn

| Giai đoạn | Nội dung | Điều kiện nghiệm thu | Ước lượng |
|---|---|---|---|
| **P0 — Audit & hợp đồng** | Codex audit editor → `capability-manifest.json` có bằng chứng; chép `core/` + registry; route `/api/ai-edit/plan` (chỉ lập plan). | Plan cho lệnh mẫu đúng như `orchestrator/examples/orchestration-plan.example.json` với manifest thật; flag OFF = baseline. | 1–2 ngày |
| **P1 — Nền tảng không AI** | 04 Cut, 02 Captions (ASS hoặc adapter V1.1), 07 loudness + fade, 08 QA tự động, vòng preview→QA. | Clip 12–20 s: không click, A/V ≤ 1 frame, −14 ± 1 LUFS, caption không bịa/không tách từ ghép, QA gate pass, BEFORE/AFTER từ cùng nguồn. | 4–6 ngày |
| **P2 — Đạo diễn & camera** | 01 Director (heuristic), 03 Camera (punch-in xen kẽ che jump cut), keyword callout qua V1.1. | Accent ≤ ngân sách; zoom không lộ viền; xem trên điện thoại thấy nhấn đúng ý chính. | 3–4 ngày |
| **P3 — Transition & phát hiện chủ thể** | 05 Transitions (restrained), subject boxes local (mặt) cho 02/03/08, scene detect. | Thời lượng không đổi; caption không che mặt; ≤ 2 transition/video ở normal. | 3–5 ngày |
| **P4 — Nâng cao, opt-in** | 06 VFX, nhạc + SFX có license, beat-sync, LLM local cho semantic cut/role, VLM review, overlay renderer cho light sweep/mask. | Mỗi tính năng có toggle riêng, đo thời gian render, rollback bằng revision. | theo nhu cầu |

**Nguyên tắc:** không mở giai đoạn sau khi giai đoạn trước chưa có video AFTER thật từ pipeline editor và QA pass.
