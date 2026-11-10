---
name: visual-quality-reviewer
description: >-
  Kiểm tra chất lượng video Shorts trước khi xuất: độ đọc phụ đề (CPS, dòng, safe area, che mặt, chữ
  bịa), nhịp cắt, mật độ hiệu ứng, transition, camera, loudness/true peak, license âm thanh, metadata
  render, frame đen/đứng, im lặng; mỗi lỗi có bằng chứng đo được và fix gửi đúng skill — không chấm điểm.
---

# Skill 08 — AI Visual Quality Reviewer

## 1. Mục đích
Chặn lỗi **quan sát/đo được** trước khi xuất bản và chỉ ra skill nào phải sửa — làm đầu vào cho vòng revise của Orchestrator.

## 2. Khi nào dùng
Sau mỗi preview và trước export cuối; khi người dùng hỏi "video ổn chưa?".

## 3. Khi nào không dùng
Không dùng để đánh giá "hay/dở" sáng tạo hay dự đoán view. Không thay cho việc người dùng xem lại.

## 4. Đầu vào
Bất kỳ section nào có: CaptionTrack, transcript output-time, CutList, DirectorDecisions, TransitionPlan, CameraTrack, AudioMixPlan, đo loudnorm bản cuối, ffprobe JSON, log blackdetect/freezedetect/silencedetect, đường dẫn output & nguồn, subject boxes.

## 5. Đầu ra
`QAReport` (`schemas/qa-report.schema.json`): `gate`, `counts`, `findings[]` (bằng chứng + `suggestedFix`), `checked`, `notChecked`, `manualReview`; contact sheet PNG.

## 6. Quy trình
1. Kiểm plan (không cần render): caption, nhịp, hiệu ứng, transition, camera, license.
2. Render preview → chạy `detect_cmds()` (ffprobe, blackdetect, freezedetect, silencedetect) + đo loudnorm.
3. Kiểm render: metadata, A/V, frame đen/đứng, im lặng, an toàn đường dẫn.
4. Contact sheet (`contact_sheet_cmd`) cho người xem.
5. `finalize()` → gate. Orchestrator gửi `suggestedFix` về skill sở hữu, render revision mới.

## 7. Công cụ
FFmpeg/ffprobe, Python stdlib. VLM local tuỳ chọn (chỉ thêm finding, không chấm điểm).

## 8. Preset / thuật toán
Bảng quy tắc `references/review-rubric.md` (QA-CAP/PACE/FX/TR/CAM/AUD/REN). Ngưỡng mặc định lấy từ preset caption và `effectBudget`.

## 9. Phối hợp
Đọc mọi section, **không sửa section nào** (CR-08). Mỗi finding có `suggestedFix.skill` = owner. Chạy lại tối đa `maxReviewIterations`.

## 10. Nghiệm thu
`python tests/test_review.py` pass: ví dụ sạch → pass; chữ bịa → blocker; ra safe area/che mặt → major; video sai fps + frame đen (render thật) → phát hiện; output ghi đè nguồn → blocker; thiếu dữ liệu → nằm trong `notChecked`.

## 11. Giới hạn
Không "thấy" bố cục thẩm mỹ, biểu cảm, lỗi ngữ nghĩa; không đo độ tương phản chữ trên từng frame (cần phân tích pixel vùng caption — hướng mở rộng); kết quả chỉ tốt bằng dữ liệu đầu vào.

## 12. Fallback
Không có render → chỉ kiểm plan, ghi `notChecked`. Không ffmpeg → chỉ kiểm plan. Skill tắt → Orchestrator vẫn yêu cầu người dùng xem contact sheet trước khi coi là xong.
