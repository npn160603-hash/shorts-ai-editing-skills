# Quy tắc âm thanh cho Shorts (speech-first)

## Mục tiêu loudness
| Preset | Integrated | True peak | LRA |
|---|---|---|---|
| shorts (YouTube Shorts/TikTok/Reels) | −14 LUFS | −1.0 dBTP | ≤ 9 LU |
| podcast clip | −16 LUFS | −1.5 dBTP | ≤ 7 LU |

Nền tảng tự chuẩn hoá lại; −14 LUFS giúp không bị kéo xuống/đẩy lên quá nhiều. Đo bằng `loudnorm print_format=json` (pass 1), áp pass 2 `linear=true` trên **bản mix cuối**.

## Giọng nói
- `highpass=f=80` (bỏ ù, tiếng gió nhẹ).
- Denoise `afftdn=nf=-25` **chỉ khi** `speechPriority` và có tiếng nền rõ; denoise mạnh làm giọng "robot".
- Không nén/EQ mạnh tự động — không biết micro nguồn.

## Nhạc nền
- Chỉ file người dùng cung cấp với `license ∈ {own, CC0, licensed}` + `licenseProof`. **Không tự tải nhạc**, không dùng nhạc thương mại không rõ quyền.
- Mức nền −18 dB, duck thêm −12 dB khi có lời (speechPriority), attack 0.25 s **trước** lời, release 0.45 s.
- Ducking bằng **đường bao âm lượng tất định** từ khoảng lời nói (không dùng sidechain đoán ngưỡng) → lặp lại được, test được.
- Fade in 0.6 s, fade out 1.2 s; loop bằng `-stream_loop -1`, cắt theo độ dài video.

## SFX
- Neo vào sự kiện hình: transition → whoosh (bắt đầu sớm 0.12 s), keyword-pop → pop, callout → tick.
- Khoảng cách ≥ 1.5 s, ≤ `maxSfxPer10s`; đè lên lời → −14 dB, không đè → −8 dB (CR-07).
- Thư viện local có license; thiếu loại → bỏ, ghi cảnh báo.

## Chuyển tiếp audio
- Mỗi điểm cắt: fade in/out 10 ms (Skill 04/05 đã làm khi trim) → hết tiếng click.
- Không crossfade lời nói qua transition (CR-06).

## Beat
- `estimate_bpm`: onset năng lượng + tự tương quan lag phân số. Đã kiểm trên click track 120 & 96 BPM (sai số ≤ 0.5 BPM). Nhạc tự do/ambient → confidence thấp → không dùng beat-sync.
- Ưu tiên BPM từ metadata/người dùng (`method: user|metadata`).
- Beat grid dùng để: căn transition/keyword-pop ±1 frame về beat gần nhất **chỉ khi** không làm lệch lời > 80 ms.

## Đồng bộ A/V
- Cut/transition đều tính theo frame; audio cắt cùng biên frame → lệch ≤ 1 frame (QA đo bằng ffprobe duration từng stream).
