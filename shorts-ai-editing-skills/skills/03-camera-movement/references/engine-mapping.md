# Map CameraTrack sang engine

## FFmpeg (đã kiểm chứng trên FFmpeg 6.1)
Chuỗi lọc do `ffmpeg_filter(track)` tạo:
```
crop=<base aspect window>            (chỉ khi nguồn khác tỉ lệ đầu ra)
scale=<out_w>:<out_h>:flags=lanczos   (chỉ khi base window ≠ output)
scale=w='trunc(OW*z(t)/2)*2':h='trunc(OH*z(t)/2)*2':eval=frame:flags=bicubic
crop=OW:OH:x='clip(cx(t)*iw-OW/2,0,iw-OW)':y='clip(cy(t)*ih-OH/2,0,ih-OH)'
setsar=1
```
- `z(t)`, `cx(t)`, `cy(t)` là biểu thức `if(lt(t,a),…)` lồng nhau, easing viết bằng toán (không code tuỳ ý).
- Chạy **sau** cut/concat (thời gian `t` là output time) và **trước** overlay caption.
- Hạn chế: crop theo pixel nguyên → move chậm có thể "lăn tăn"; punch-in tức thì không bị.

## Remotion / Canvas / WebGL
- Dùng `sample(track, duration)` → `[frame, zoom, cx, cy]`; áp `transform: scale(z) translate(...)` trên layer video với `transform-origin` = tâm cửa sổ. Subpixel → mượt hơn.
- Hoặc nội suy runtime bằng cùng công thức `state_at` (port 30 dòng sang TS) — kiểm tra 5 frame trùng giá trị với Python (sai số < 1e-4).

## Python/OpenCV
- Mỗi frame: tính cửa sổ (x,y,w,h) từ `state_at`, `cv2.resize` vùng crop về OW×OH bằng `INTER_CUBIC` (hoặc `warpAffine` cho subpixel).
