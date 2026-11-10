# Thứ tự thực thi và lý do

```
probe → transcript → cut → (remap transcript to output time) → direct
      → captions ┐
      → camera   ┼→ transitions → vfx → audio → compile-overlays → conflict-check
                 ┘
      → preview (540×960) → qa → revise (≤ maxIterations) → export (1080×1920) → report
```

| Stage | Vì sao ở vị trí này |
|---|---|
| cut trước tất cả | Cut đổi timebase. Mọi skill sau làm việc trên **output time**; làm ngược sẽ phải remap mọi thứ. |
| direct sau cut | Director cần nhịp thật sau khi bỏ khoảng lặng để phân bổ accent đúng. |
| captions ∥ camera | Độc lập về dữ liệu: cùng đọc `directorDecisions`. Có thể chạy song song. |
| transitions sau camera | Transition phải biết mức zoom hai bên cut để chọn match/hard cut (CR-02). |
| audio sau transitions + captions | SFX neo vào transition/keyword-pop; crossfade cần danh sách ranh giới cut cuối cùng. |
| compile-overlays (Motion Designer V1.1) | Tái sử dụng schema `ShortsMotionPlan` có sẵn, không tạo engine overlay mới. |
| conflict-check | Chỉ một chỗ áp CR-01…CR-10, tránh mỗi skill tự "nhường" theo kiểu khác nhau. |
| preview → qa → revise | QA phải nhìn video thật (preview), không chỉ plan. |

## Vòng sửa (revise)

1. QA trả `findings[]`, mỗi finding có `suggestedFix.skill` + `action` + `params`.
2. Orchestrator gom fix theo owner, chạy lại **chỉ** các skill đó và các skill phụ thuộc phía sau.
3. `revision += 1`, render preview mới vào thư mục mới.
4. Dừng khi không còn `blocker`/`major` hoặc chạm `maxIterations` → báo cáo finding còn lại, không giấu.

## Hành vi khi skill bị tắt

- `skipped`: section ghi `status: "skipped"`; stage không chạy; pipeline cũ giữ nguyên ở phần đó.
- `fallback`: chạy chế độ giảm cấp (vd. caption theo cụm, transition chỉ hard cut).
- `blocked`: capability có công thức nhưng chưa có runtime → Codex phải tích hợp trước; lúc chạy coi như `skipped`.
- Tắt **tất cả** skill ⇒ output phải giống baseline của editor (test hồi quy bắt buộc).
