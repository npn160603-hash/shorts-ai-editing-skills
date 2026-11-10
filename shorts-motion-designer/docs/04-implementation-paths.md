# 04 — Tích hợp theo engine thực tế

## Path A — Editor đã dùng Remotion

1. Audit dependency của editor đích, license và môi trường render thực tế; không tự copy `node_modules`.
2. Giữ composition hiện có, video/audio source, clip offsets, FPS; thêm `<MotionOverlay>`/track ở mức compositing phù hợp.
3. Chuyển `ShortsMotionPlan` sang layer/keyframe runtime của chính editor đích; tận dụng các module nội bộ đã có nếu tương thích.
4. Tránh render text browser và text SVG với metrics không đồng nhất mà không test.
5. P0 test 1 scene 9:16, caption grapheme + opacity/translation.

## Path B — Editor dùng FFmpeg (không Remotion)

Lựa chọn ít xâm lấn:

- Render animation thành **RGBA PNG sequence** ở đúng `fps`/resolution (ngốn IO, phù hợp prototype ngắn), hoặc video overlay với codec hỗ trợ alpha sau khi kiểm chứng.
- Composite bằng `overlay` trong FFmpeg, giữ audio video gốc và timeline output.
- Cần đảm bảo pixel format alpha, gamma/opacity và animation frame mapping; định dạng MP4 H.264 tiêu chuẩn **không giữ alpha channel** cho overlay trung gian.
- Không tạo video black background rồi `overlay` nếu background chưa được key/alpha, sẽ che mất footage.
- FFmpeg `drawtext`/ASS phù hợp cho subtitle, nhưng animation typography từng grapheme có thể cần render overlay riêng.

Ví dụ **minh họa** filter (phải thay file, mapping stream, pixel format và codec thực tế):

```bash
ffmpeg -i base.mp4 -framerate 30 -i overlay_%05d.png -filter_complex "[0:v][1:v]overlay=0:0:format=auto:shortest=1[v]" -map "[v]" -map 0:a? -c:v libx264 -pix_fmt yuv420p -c:a copy output.mp4
```

Không chạy lệnh này nguyên xi với file riêng của người dùng. Không dùng `-y` ghi đè output.

## Path C — Python/OpenCV/MoviePy

- Giữ API service và job queue hiện tại; đưa plan thành data object và render overlay riêng.
- Kiểm soát RGB/BGR, RGBA, alpha compositing, font Unicode và frame/time mapping.
- Không dùng PIL font có thiếu tiếng Việt hoặc text measurement sơ sài rồi tuyên bố typography đạt.
- Chỉ thêm Remotion service nếu đo được giá trị và chi phí hệ thống; không mở microservice không cần thiết.

## Path D — Client-only web

- Xác định editor dựa HTML Canvas/WebGL/WebCodecs hay preview-only. Không cho rằng UI preview là render cuối.
- Với output cần backend/worker, thiết kế giao thức job từ browser sang service local rõ ràng, retry/cancel/progress và sandbox file paths.
- Ưu tiên bảo toàn UX hiện tại, không đưa API key vào browser.

## Adapter contract đề xuất (minh họa)

```ts
interface MotionIntegrationAdapter {
  validate(plan: ShortsMotionPlan): ValidationResult;
  buildOverlayTrack(plan: ShortsMotionPlan, context: RenderContext): OverlayTrack;
  renderPreviewFrame(frame: number, context: RenderContext): Promise<PreviewFrame>;
}
```

Đây là **ý tưởng interface**, không phải type có sẵn trong source. Codex phải điều chỉnh theo kiến trúc thật.

## Các tầng phải tách biệt

1. Analysis/Director: chọn *lúc nào* cần hiệu ứng và *vì sao*.
2. Motion plan: JSON đã validate; không chứa code thực thi tùy ý.
3. Adapter: map từ plan sang renderer đích.
4. Renderer/compositor: tạo pixel/clip.
5. QA: thực hiện A/B, frame review, ffprobe, compatibility.

Việc có `SKILL.md` **không** đồng nghĩa runtime tự biết render. Nếu target thiếu renderer, phải xây adapter và kiểm thử thật.
