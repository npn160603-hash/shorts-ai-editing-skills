---
name: audio-director
description: >-
  Đạo diễn âm thanh cho Shorts, ưu tiên giọng nói: high-pass/denoise nhẹ, loudness hai lượt −14 LUFS,
  nhạc nền có license với ducking tất định theo lời, SFX neo vào transition/keyword-pop từ thư viện
  có license, beat grid nhẹ không cần AI, fade chống click ở điểm cắt; xuất AudioMixPlan + filter FFmpeg.
---

# Skill 07 — Audio Editing Director

## 1. Mục đích
Giọng nói **rõ, đều, đúng chuẩn loudness**; nhạc/SFX chỉ hỗ trợ, không lấn lời, không vi phạm bản quyền.

## 2. Khi nào dùng
Mọi bản export có audio (ít nhất phần loudness). Nhạc/SFX chỉ khi người dùng cho phép và cung cấp tài nguyên có license.

## 3. Khi nào không dùng
Video đã được mix chuyên nghiệp (người dùng tắt); video ASMR/âm thanh hiện trường cần giữ nguyên động.

## 4. Đầu vào
Thời lượng output, khoảng lời nói (output time), capability `audio.*`, `speechPriority`, file nhạc + license, thư viện SFX (`schemas/sfx-library.schema.json`), anchor từ Transitions/Director, BPM (tuỳ chọn).

## 5. Đầu ra
`AudioMixPlan` (`schemas/audio-mix-plan.schema.json`), `ffmpeg_mix_graph()` → `[amix]`, lệnh đo `measure_cmd()`.

## 6. Quy trình
1. Chuỗi giọng: highpass (+ afftdn nếu speechPriority & có cap).
2. Gộp khoảng lời (cầu nối 0.6 s) → vùng duck.
3. Nhạc: kiểm license → gain, envelope duck, fade, loop/trim.
4. SFX: kiểm license thư viện → đặt theo anchor, khoảng cách, ngân sách, gain theo lời.
5. Mix `amix normalize=0` → đo loudnorm (pass 1) → pass 2 `linear=true` → 48 kHz.
6. Báo cáo cảnh báo (nhạc bị từ chối, SFX thiếu loại…).

## 7. Công cụ
FFmpeg (`highpass`, `afftdn`, `volume eval=frame`, `adelay`, `amix`, `loudnorm`, `afade`). Python stdlib (đọc PCM để ước lượng BPM). Không model, không API.

## 8. Preset / thuật toán
`TARGETS` (shorts/podcast), duck −12 dB/0.25 s/0.45 s, `references/audio-rules.md`.

## 9. Phối hợp
- Không cắt khoảng lặng (Skill 04 sở hữu cut).
- SFX neo vào `TransitionPlan` (type ≠ cut) và accent `keyword-pop`/`callout` của Director (CR-07).
- QA (Skill 08) đo lại loudness/true peak bản cuối.

## 10. Nghiệm thu
- `python tests/test_audio.py` pass: mix thật đạt −14 ± 1 LUFS, TP ≤ −1 dBTP (đo lại sau mix), duration audio = video; ducking gain đúng tại 3 thời điểm; BPM click track 120 ±1.
- Nghe: lời rõ hơn nhạc ở mọi chỗ; không click ở điểm cắt; SFX không đè âm tiết nhấn.

## 11. Giới hạn
Không tách giọng khỏi nhạc có sẵn (cần model source separation); denoise afftdn hạn chế với tiếng ồn biến đổi; BPM heuristic chỉ cho nhạc nhịp đều; không đo được "cảm giác" mix.

## 12. Fallback
Không loudnorm → chỉ đo & cảnh báo; không duck → không chèn nhạc; không thư viện/license → không SFX. Skill tắt → audio sau cắt giữ nguyên.
