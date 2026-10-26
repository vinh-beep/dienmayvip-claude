# Kiểm tra tồn đọng thật (0 token)

`ton_dong.py` đọc 2 tab của sheet "DMV Tong Hop Gia Theo ParentSKU" đã xuất CSV (tab TỔNG HỢP và LỊCH SỬ) và trả lời:

1. **Dữ liệu còn mới không?** Nếu bản chụp cuối quá 2 ngày, mọi kết luận về hàng đồng bị đánh dấu không đáng tin, mã thoát là 2.
2. **Tồn HTsoft mọi kho lớn hơn tồn bán sàn bao nhiêu** (hàng nằm ngoài kho bán hoặc thiếu IMEI), kèm giá trị ước tính theo giá lẻ công khai. SIM không tính giá trị.
3. **Mã có tồn mà số tồn bán sàn không đổi ≥ N ngày** (mặc định 14).

```
python ton_dong.py --tong-hop tong-hop.csv --lich-su lich-su.csv --ra ket-qua --ngay-dong 14
```

Chỉ đọc các cột bán hàng (ParentSKU, tên, tồn, giá lẻ). Mọi cột khác, kể cả cột nội bộ, bị bỏ qua và không xuất hiện trong kết quả. Giá trị chỉ là ước tính theo giá lẻ, không phải giá vốn.

Xuất CSV: mở sheet, chọn tab, Tệp → Tải xuống → CSV. Hoặc cho PC xuất thẳng từ SQL cùng định dạng cột.

Kiểm thử: `python -m pytest -q` (21 ca).
