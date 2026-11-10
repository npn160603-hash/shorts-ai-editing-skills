# Tích hợp Skill 08
1. Sau mỗi preview render: chạy `detect_cmds(preview)` + `measure_cmd` (Skill 07) → `check_*` → `finalize`.
2. Lưu `qa-report.json` + `contact_sheet.png` vào `ai-edit/rev-<n>/`; UI hiển thị finding theo timeline (click → nhảy tới `timeRange`).
3. Nút "Sửa tự động" = Orchestrator chạy lại skill trong `suggestedFix`; nút "Bỏ qua" ghi lý do người dùng (finding vẫn lưu).
4. Export bị chặn nếu có blocker (trừ khi người dùng xác nhận rõ ràng — ghi vào report).
