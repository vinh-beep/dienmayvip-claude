# nhac-cat — Trợ giúp nhanh (F1)

Kiểm kế hoạch cắt nhạc cho video trước khi dựng: đọc độ dài thật của tệp, kiểm bản quyền, mỗi SP một bài. Chi tiết: `README.md`.

| Việc | Lệnh |
|---|---|
| Kiểm kế hoạch | `python kiem_cat_nhac.py --ke-hoach gan-nhac.json --ra ket-qua --goc-ban-quyen "D:\MP3"` |
| Tự kiểm (không cần nhạc thật) | `python kiem_cat_nhac.py --kiem` → phải in `KIỂM: ĐẠT` |

Mã thoát: 0 mọi mục đạt · 1 có mục hỏng hoặc lỗi đọc kế hoạch.

Luật (26/10): đoạn mở 0–3 s · video 15–20 s · cao trào `tong_giay − 0.15` phải nằm trong độ dài thật của bài · mỗi SP một bài riêng · bản quyền rõ khi tệp trong `--goc-ban-quyen` hoặc tên có "Suno".

Cần `ffprobe` để đọc độ dài MP3/M4A. WAV đọc thẳng header, không cần công cụ ngoài.
