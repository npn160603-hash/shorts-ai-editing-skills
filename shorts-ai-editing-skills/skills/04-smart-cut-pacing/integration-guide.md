# Tích hợp Skill 04

1. **Capability**: `timeline.cutList` phải `implemented` (editor đã có trim/concat). Nếu editor có trim theo danh sách đoạn → adapter chỉ map `segments[]` sang API đó.
2. **Chưa có**: dùng `ffmpeg_concat_filter(cut_list)`:
   `ffmpeg -i input.mp4 -filter_complex "<filter>" -map "[vout]" -map "[aout]" -c:v libx264 -crf 18 -c:a aac out/rev-<n>/cut.mp4`
   (không dùng `-y`; đường dẫn revision mới).
3. **Remap** transcript bằng `remap_transcript` và lưu bản output-time; mọi skill sau đọc bản này.
4. **UI**: hiển thị danh sách `removed` (lý do + method) có checkbox khôi phục từng mục → chạy lại `build_cut_list` với removal đã lọc.
5. **Toggle**: Skill tắt ⇒ CutList identity `[{srcStartSec:0, srcEndSec:duration}]`.
6. **Test trên editor**: render clip 12–20 s; nghe từng ranh giới cut; ffprobe duration = `stats.outputDurationSec` ± 1 frame.
