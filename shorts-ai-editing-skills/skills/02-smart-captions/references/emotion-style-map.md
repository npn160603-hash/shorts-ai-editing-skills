# Animation theo cảm xúc / ngữ nghĩa

| Tín hiệu (đo được) | captionMode / animationIn | Highlight |
|---|---|---|
| Hook (Director `captionMode: headline`) | `hook-reveal` (scale 0.85→1 + fade 90 ms), font ×1.2, đặt vùng trên | từ đang nói + keyword |
| Câu cảm thán `!` | `scale-pop` | keyword |
| Câu hỏi `?` | `soft-slide-up` | từ để hỏi không cần nhấn |
| Đoạn chân thành (`calm`) | `fade-in`, preset `boxed-calm`, không scale từ | chỉ đổi màu nhẹ hoặc tắt |
| Số liệu (`number`) | giữ animation trang, tô màu số + đơn vị | màu keyword |
| CTA | `soft-slide-up`, không pop | động từ CTA (nếu là keyword) |

Nguồn "cảm xúc" ở v1 là **dấu câu + Director**, không phải mô hình nhận diện cảm xúc. Nếu có LLM, nó chỉ được đổi `captionMode` theo enum, không chèn chữ mới.
