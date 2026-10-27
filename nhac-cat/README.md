# Kiểm cắt nhạc cho video — đọc lại độ dài thật, 0 token

App E15 Nhạc DienmayVIP (PC) gán mỗi ParentSKU một bài và tính điểm cắt. Bộ này kiểm lại kế hoạch đó trước khi dựng video, theo đúng luật đã chốt 26/10:

- Đoạn mở 0–3 s, cao trào dài `tong_giay − 0.15`, video 15–20 s.
- `nhac_tu + cao trào` phải nằm trong **độ dài thật** của tệp (WAV đọc header, loại khác dùng `ffprobe`), không tin số trong kế hoạch.
- Mỗi SP một bài riêng: một bài gán cho nhiều SP bị báo.
- Bản quyền: chỉ coi là rõ khi tệp nằm trong thư mục `--goc-ban-quyen` (ví dụ `D:\MP3`) hoặc tên có "Suno"; còn lại báo "chưa rõ bản quyền".

```
python kiem_cat_nhac.py --ke-hoach "C:\AIVIP\state\nhac-vip\gan-nhac.json" --ra ket-qua --goc-ban-quyen "D:\MP3"
```
Kế hoạch là JSON: `[{"sku","tep","doan_mo_giay","nhac_tu","tong_giay"}]`. Ghi `kiem-cat-nhac.md` và `.json`; mã thoát 1 nếu có mục hỏng.

Không tạo nhạc, không gọi Suno hay AI nào. Kiểm thử: `python -m pytest -q` (12 ca, WAV sinh bằng thư viện chuẩn).
