# Điểm cắm AI (tuỳ chọn)

Director chạy được hoàn toàn bằng heuristic. LLM local chỉ **bổ sung đầu vào**, không bỏ qua ngân sách.

`analyze(..., ai_overrides={segmentId: {...}})` nhận:
```json
{"s4": {"role": "climax", "importance": 0.9, "keywords": ["25 phút"], "sincere": false}}
```
Ràng buộc kiểm tra sau khi nhận từ LLM:
- `keywords` phải là chuỗi con có thật trong `text` của segment (so sau khi NFC + lowercase) — nếu không, loại.
- `importance` ∈ [0,1]; `role` thuộc enum schema.
- Không chấp nhận mã/biểu thức trong JSON.

Prompt gợi ý: "Cho danh sách câu (id, text). Trả JSON thuần: role (hook/setup/point/proof/climax/payoff/cta), importance 0–1, tối đa 2 keyword là cụm có nguyên văn trong câu, sincere true/false. Không thêm chữ ngoài JSON."
