# Danh mục chuyển cảnh — khi nào dùng

**Mặc định của Shorts nói chuyện là CUT.** Transition là ngoại lệ có lý do.

| type | xfade (FFmpeg ≥ 6.0) | Thời lượng | Dùng khi | Không dùng khi |
|---|---|---|---|---|
| cut | — | 0 | Jump cut cùng shot (camera reframe che) | — |
| smooth-cut | fade | 0.12–0.2 s | Hai shot gần giống nhau, cut bị "giật" | Mỗi cut (thành mờ nhoè) |
| swipe-left / right | smoothleft / smoothright | 0.25–0.35 s | Sang ý/mẹo tiếp theo (trái = tiến), quay lại (phải) | Giữa câu |
| swipe-up | smoothup | 0.25–0.3 s | Sang phần mới, cảm giác "cuộn" dọc | Trong hook |
| zoom | zoomin | 0.25–0.35 s | Vào climax / reveal | Khi camera đang punch (CR-02) |
| blur | hblur | 0.2–0.3 s | Bỏ qua thời gian, chuyển chủ đề nhẹ | Video giáo dục cần rõ ràng |
| mask-reveal | circleopen | 0.3–0.4 s | Before/after, tiết lộ | Lặp lại nhiều lần |
| shape-reveal | rectcrop | 0.3 s | Chuyển sang cảnh có khung/UI | — |
| directional-wipe | wipeup | 0.25–0.3 s | Đồng bộ hướng chuyển động có sẵn | — |
| dip-to-black | fadeblack | 0.4 s | Kết chuyện/khoảng lặng mạnh | Shorts loop |
| motion-match | — | — | **Cần AI/CV** (optical flow, tracking) — v1 không có runtime | — |

## Ràng buộc kỹ thuật (bắt buộc)
- **Không đổi thời lượng & không dời lời**: transition mượn d/2 frame "handle" từ đoạn đã cắt ở mỗi bên. Thiếu handle → cut.
- Audio giữ nguyên điểm cắt (fade 10 ms), **không** crossfade lời nói.
- Không trong hook (CR-03); không khi lời rơi vào nửa giữa cửa sổ (CR-06); camera đang move → cut (CR-02).
- Tối đa `maxVisualTransitions` (subtle 1, normal 2, dynamic 4) cho cả video.
- Cùng một video chỉ dùng **1–2 kiểu** transition để nhất quán.
