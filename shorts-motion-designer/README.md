# SHORTS MOTION DESIGNER — SKILL ĐỘC LẬP CHO LOCAL WEB EDITOR

**Mục tiêu:** Cung cấp cho Codex một bộ nguyên tắc dựng video Shorts, hợp đồng dữ liệu, hiệu ứng mẫu, cách thiết kế adapter và checklist nghiệm thu để nâng cấp **chính công cụ edit Shorts đang mở trên máy**. Không cần dự án, source code hay thư mục bên ngoài.

**Lưu ý:** Đây là gói **kiến thức + hướng dẫn triển khai + JSON Schema và ví dụ**, KHÔNG phải plugin render đã biên dịch và KHÔNG tự động hoạt động ngay sau khi giải nén. Codex cần đọc source của editor đích và viết/mở rộng adapter theo engine thực tế. Mọi nội dung có thể đọc offline.

## Bên trong

- `SKILL.md`: Skill hướng dẫn AI/Codex lựa chọn hiệu ứng và triển khai.
- `CODEX_START_HERE.md`: Prompt giao việc trong repository editor đích.
- `docs/`: Audit, timeline contract, creative rules, integration paths, QA, roadmap và các công thức motion độc lập.
- `schemas/shorts-motion-plan.schema.json`: Schema trung gian để trao đổi kế hoạch dựng.
- `examples/`: Kế hoạch edit mẫu, preset mẫu, checklist nghiệm thu.
- `scripts/check_package.py`: Kiểm tra gói và ví dụ với Python standard library.
- `install.ps1`: Cài tài liệu vào `.agents/skills` trong repo đích, tùy chọn, không ghi đè.

## Sử dụng ngay (Windows)

1. Giải nén ZIP, ví dụ vào `D:\Skill-Packs\shorts-motion-designer`.
2. Mở Codex trong **thư mục gốc của chính tool edit video Shorts**.
3. Bảo Codex đọc `SKILL.md` và `CODEX_START_HERE.md` bằng đường dẫn thực tế vừa giải nén.
4. Codex audit stack hiện có, giữ nguyên tính năng đang chạy, xây adapter nhỏ với cờ bật/tắt.
5. Yêu cầu render BEFORE và AFTER từ cùng clip, kiểm tra video thật rồi mới nghiệm thu.

Cài Skill vào dự án (không bắt buộc):

```powershell
powershell -ExecutionPolicy Bypass -File "D:\Skill-Packs\shorts-motion-designer\install.ps1" -ProjectPath "D:\DUONG-DAN-TOOL-SHORTS"
```

## Những gì gói có thể giúp triển khai

- Motion keyframes (position/scale/rotation/opacity), interpolation và easing.
- Typography theo toàn dòng/từng từ/từng grapheme, chú ý tiếng Việt Unicode.
- Word-aligned captions **nếu editor đã có word timestamps**; fallback theo phrase nếu không.
- Hook title, kinetic subtitles, callouts, lower-third và CTA.
- Motion presets, nhóm layer và parenting như các **mô hình kỹ thuật** để Codex xây tương thích vào engine đích.
- Quy tắc dựng Shorts, bố cục an toàn 9:16, kiểm tra cut/timestamp/audio.

Mask/glow/camera/VFX chỉ là mục tiêu nâng cấp tùy khả năng engine hiện có, không phải tính năng đã cài sẵn. Gói không cung cấp nhận diện giọng nói, beat detection hay AI video generation.

## Quy tắc an toàn

- **Chỉ thao tác trong repository tool edit Shorts hiện tại.** Không yêu cầu mã nguồn dự án khác.
- Không xóa, reset, stash, clean hay ghi đè dữ liệu người dùng.
- Không tự ý cài dependency lớn, gọi API trả phí hoặc upload clip lên internet.
- Không thay engine render khi adapter/overlay là đủ.
- Không tuyên bố tích hợp thành công chỉ vì tạo JSON hoặc test pass; phải xuất video thật từ pipeline đích.
