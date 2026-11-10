# Hợp đồng chung giữa các Skill

## Thời gian
- Giây (float) trong JSON; render lượng tử hoá `frame = round(t × fps)`; khoảng `[start, end)`.
- `timebase: "source"` chỉ tồn tại **trước** Skill 04. CutList là artefact duy nhất đổi timebase. Sau đó mọi section là `"output"`.
- Không có cut → CutList identity (1 segment) để mọi skill sau vẫn chạy cùng một đường code.
- Trim video theo **frame index** (nguồn CFR; VFR phải chuẩn hoá trước — như V1.1 đã yêu cầu).

## Toạ độ
- Chuẩn hoá `[0..1]`, gốc trên-trái, `y` hướng xuống (giống V1.1). Safe area là cấu hình, không hard-code.
- Subject box: `{startSec, endSec, box:{x,y,w,h}, label}`.

## Quyền sở hữu section (CR-08)
| Section | Owner |
|---|---|
| transcript (source) | editor (ASR có sẵn) |
| cutList, transcript@output | smart-cut-pacing |
| contentAnalysis, directorDecisions | editing-director |
| captionTrack | smart-captions |
| cameraTrack | camera-movement |
| transitionPlan | advanced-transitions |
| vfxPlan | cinematic-vfx |
| audioMixPlan | audio-director |
| motionPlan (ShortsMotionPlan v1.0) | shorts-motion-designer (V1.1, tái sử dụng) |
| qaReport | visual-quality-reviewer |

Skill khác muốn thay đổi → tạo `suggestedFix` cho owner; Orchestrator chạy lại owner.

## Revision & rollback
- Mỗi lần chạy: `ai-edit/rev-<n>/` mới chứa mọi JSON + preview + report. Không ghi đè nguồn, không ghi đè revision cũ.
- Rollback = chọn `rev-<n>` cũ. Gỡ = tắt registry/flag; đường code cũ của editor không đổi.

## An toàn dữ liệu cấu hình
- JSON chỉ chứa dữ liệu khai báo; mọi filter FFmpeg được **sinh từ template whitelist + số đã kẹp**, không nhận chuỗi filter tự do từ JSON/LLM.
- Mọi đầu ra từ LLM (intent, role, keyword, semantic cut) là **dữ liệu cần kiểm** (enum, có trong transcript, trong ngân sách).
