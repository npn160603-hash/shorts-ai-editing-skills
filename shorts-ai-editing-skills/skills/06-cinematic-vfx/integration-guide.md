# Tích hợp Skill 06
1. Manifest: đánh dấu `vfx.colorAdjust`, `vfx.blur`, `vfx.glow`, `vfx.motionBlur` = implemented chỉ sau khi render thử `ffmpeg_chain` trên editor.
2. Vị trí trong graph: `[cut/transition] → camera → VFX → captions(ASS/overlay) → encode`.
3. Đo `render seconds / output seconds` trên máy người dùng 1 lần; ghi `hardware.maxRenderSecondsPerOutputSecond`.
4. Toggle OFF (mặc định) → bỏ chuỗi VFX.
