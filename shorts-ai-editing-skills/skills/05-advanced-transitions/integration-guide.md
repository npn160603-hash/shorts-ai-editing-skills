# Tích hợp Skill 05
1. Kiểm `ffmpeg -h filter=xfade` có các tên trong `CATALOG` → `transition.xfade = implemented`.
2. Thay bước concat của editor bằng `ffmpeg_graph(cut_list, plan)` **chỉ khi** plan có ít nhất 1 transition visual; ngược lại giữ concat cũ.
3. Camera filter áp lên `[vout]` sau graph này (t = output time).
4. Toggle OFF → dùng `ffmpeg_concat_filter` của Skill 04 (kết quả thời lượng y hệt).
5. Test: ffprobe số frame & thời lượng audio bằng bản không transition; trích frame tại `atSec ± d/2`.
