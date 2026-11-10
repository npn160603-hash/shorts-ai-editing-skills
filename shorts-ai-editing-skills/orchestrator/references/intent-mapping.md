# Diễn giải yêu cầu người dùng → intent

Parser trong `lib/orchestrate.py` chạy offline (không cần model): bỏ dấu, lowercase, so khớp từ khóa VI/EN.
Nếu editor có LLM local, LLM chỉ được phép **điền `intent`** theo `schemas/edit-request.schema.json`; `intent` có cấu trúc luôn ghi đè keyword parser.

| Người dùng nói | intent |
|---|---|
| "cắt đoạn thừa", "bỏ khoảng lặng", "jump cut", "tighten" | `cut: true` |
| "phụ đề động", "caption", "chữ động", "karaoke" | `captions: true` |
| "zoom đoạn quan trọng", "punch in", "cận cảnh" | `camera: true` |
| "chuyển cảnh" | `transitions: true` |
| "glow", "light sweep", "VFX" | `vfx: true` (skill vẫn opt-in trong registry) |
| "giữ giọng nói rõ", "clear voice" | `speechPriority: true`, `audio: true` |
| "nhạc nền", "ducking" | `music: true` (cần `constraints.allowMusic` + file nhạc có license) |
| "SFX", "whoosh" | `sfx: true` (cần `constraints.allowSfx` + thư viện có license) |
| "vừa phải", "cân bằng" | `intensity: normal` |
| "nhẹ nhàng", "tinh tế", "tối giản" | `intensity: subtle` |
| "sôi động", "mạnh", "hype" | `intensity: dynamic` |
| "chuyên nghiệp" | `style: professional` → luôn bật audio hygiene + transition restrained khi có cut |

Mặc định khi không nói gì: `style: professional`, `intensity: normal`.

**Phạm vi được phép** nằm trong `constraints` (vd. `maxRemovedRatio`, `allowReorder`, `forbiddenEffects`). Orchestrator không bao giờ vượt `constraints`, kể cả khi intent "muốn".
