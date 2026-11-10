# Bộ quy tắc QA (dựa trên lỗi quan sát được — không chấm điểm cảm tính)

Mỗi finding = `ruleId` + **bằng chứng đo được** + ngưỡng + khoảng thời gian + `suggestedFix` gửi về skill sở hữu.
Cổng nghiệm thu: **0 blocker và 0 major**. Không có "điểm đẹp /10".

| Rule | Mức | Kiểm tra | Nguồn dữ liệu | Fix gửi về |
|---|---|---|---|---|
| QA-CAP-01 | major | CPS trang > maxCps | CaptionTrack | captions: preset ít chữ/trang |
| QA-CAP-02 | minor | trang < 0.3 s | CaptionTrack | captions: gộp trang |
| QA-CAP-03 | major | > 2 dòng | CaptionTrack | captions |
| QA-CAP-04 | major | khối chữ ra ngoài safe area | CaptionTrack | captions: re-place |
| QA-CAP-05 | major | che subject box > 15% | CaptionTrack + boxes | captions: re-place |
| QA-CAP-06 | **blocker** | chữ không có trong transcript (bịa) | CaptionTrack + transcript | captions: rebuild |
| QA-CAP-07 | major | trang chồng thời gian / quá cuối video | CaptionTrack | captions |
| QA-CAP-08 | major | từ highlight nằm ngoài thời gian trang | CaptionTrack | captions |
| QA-PACE-02 | major | hai cut cách < 0.5 s (nháy) | CutList | cut: minKeepSec |
| QA-PACE-03 | minor | khoảng chết > 0.5 s trước lời đầu | transcript | cut: trim head |
| QA-PACE-04 | **blocker** | cắt vượt `maxRemovedRatio` | CutList | cut |
| QA-FX-01 | major | accent/10 s vượt ngân sách (overlay hoặc camera) | DirectorDecisions | director |
| QA-TR-01 | major | transition trong hook | TransitionPlan | transitions |
| QA-TR-02 | major | số transition > ngân sách | TransitionPlan | transitions |
| QA-TR-03 | minor | > 2 kiểu transition (thiếu nhất quán) | TransitionPlan | transitions |
| QA-CAM-01 | major | zoom > maxZoom | CameraTrack | camera |
| QA-CAM-02 | major | move camera chồng nhau | CameraTrack | camera |
| QA-AUD-01 | major | loudness lệch > 1 LU hoặc true peak > trần | đo loudnorm bản cuối | audio |
| QA-AUD-02 | **blocker** | nhạc/SFX không có license chấp nhận | AudioMixPlan | audio: bỏ |
| QA-REN-01 | **blocker** | sai độ phân giải/fps/không có video | ffprobe | orchestrator: export settings |
| QA-REN-02 | major | lệch thời lượng A/V > 1 frame / mất audio | ffprobe | cut: trim frame-exact |
| QA-REN-03 | major | frame đen | blackdetect | camera/transition |
| QA-REN-04 | minor | hình đứng > 1.5 s | freezedetect | — (xem tay) |
| QA-REN-05 | minor | im lặng > 1.2 s trong output | silencedetect | cut |
| QA-REN-06 | **blocker** | output trùng file nguồn (ghi đè) | đường dẫn | orchestrator |

`notChecked` liệt kê mọi kiểm tra không chạy được vì thiếu dữ liệu — **không bao giờ coi là đạt**.

## Kiểm tra cần mắt người (luôn có trong báo cáo)
1. Xem 1 lần có tiếng, 1 lần tắt tiếng, ở cửa sổ cỡ điện thoại.
2. Contact sheet mỗi 0.5 s + frame tại mỗi cut và đầu mỗi trang caption.
3. Dấu tiếng Việt hiển thị đủ (không ô vuông), không cụt glyph cuối dòng.
4. Từ highlight khớp lời ở 3 điểm ngẫu nhiên (±2 frame).

## Vision model (tuỳ chọn)
Nếu có VLM local: đưa contact sheet + danh sách timestamp, yêu cầu trả **finding theo schema** (`source: "vision-model"`, có `timeRange` và mô tả cái nhìn thấy). Không cho VLM cho điểm; finding VLM mặc định `minor` cho đến khi người xác nhận.
