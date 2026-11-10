---
description: Dựng video Shorts/TikTok/Reels tự động (shorts-ai-editing-skills)
---
Người dùng muốn dựng video ngắn. Yêu cầu nguyên văn: $ARGUMENTS

Làm đúng theo `.opencode/skills/shorts-ai-editing-skills/AGENTS.md`:
1. Xác định file video trong yêu cầu (hỏi lại nếu không rõ file nào).
2. Chạy `python .opencode/skills/shorts-ai-editing-skills/scripts/shorts.py edit "<video>" --instruction "<yêu cầu>"` với tham số phù hợp; video dài thì thêm `--detach` và theo dõi bằng lệnh `status`.
3. Báo lại đường dẫn video, những gì đã làm, lỗi còn lại.
Không ghi đè file gốc, không cài thư viện hay dùng nhạc khi chưa được người dùng đồng ý.
