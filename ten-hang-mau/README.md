# Đổi tên máy Samsung: thêm màu tiếng Anh (màu in trên hộp) + mã máy

Quy tắc: `[Loại] SAMSUNG [Model] [RAM] [ROM] [Màu VN] [Màu EN] [Mã máy]`
Ví dụ: `ĐTDĐ SAMSUNG A07 5G 4GB 128GB Tím Light Violet SM-A076BLVBXXV`

- Màu EN lấy từ 2 ký tự ngay sau model trong mã máy. Z = màu cơ bản (ZK Black, ZG Green), L = Light (LV Light Violet, LG Light Green), D = Dark, A = Absolute.
- Từ điển trong `doi_ten_samsung.py` đã khớp 100% với bảng ghép mã của HTSoft. Gặp mã mới thì dòng đó vào nhóm "Cần xác nhận" để đọc màu trên hộp.
- Script **chỉ đọc**. Nó xuất Excel với 3 nhóm: Đổi ngay · Cần xác nhận · Thiếu mã máy. Chủ shop duyệt xong, phiên PC mới sửa tên trong HTSoft (sao lưu trước, TRAN + TRY/CATCH).
- Không đưa dữ liệu tồn hay tên hàng thật vào repo này (repo công khai). Dữ liệu và kết quả để trên Bridge.

Chạy: `python doi_ten_samsung.py ban-chup.json ra.xlsx`. Kiểm thử: `python test_doi_ten_samsung.py`
