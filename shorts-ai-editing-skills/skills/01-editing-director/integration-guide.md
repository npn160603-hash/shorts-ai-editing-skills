# Tích hợp Skill 01

1. Không cần capability render. Cần transcript output-time.
2. Backend gọi `analyze()` rồi `decide()` với `effectBudget` lấy từ OrchestrationPlan.
3. Lưu `content-analysis.json`, `director-decisions.json` vào `ai-edit/rev-<n>/`.
4. UI gợi ý: timeline hiển thị accent dạng marker + `dropped` dạng marker mờ; người dùng kéo/xoá marker → ghi `roleSource: manual`, các skill sau đọc lại.
5. Toggle OFF: ghi `directorDecisions.status = "skipped"`; Captions/Camera/Audio chạy chế độ plain.
