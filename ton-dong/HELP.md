# ton-dong — Trợ giúp nhanh (F1)

Kiểm tồn đọng thật từ sheet "DMV Tong Hop Gia Theo ParentSKU" (2 tab xuất CSV). Chi tiết: `README.md`.

| Việc | Lệnh |
|---|---|
| Chạy | `python ton_dong.py --tong-hop tong-hop.csv --lich-su lich-su.csv --ra ket-qua` |
| Đổi ngưỡng ngày đứng | thêm `--ngay-dong 21` (mặc định 14) |
| Tự kiểm (không cần tệp) | `python ton_dong.py --kiem` → phải in `KIỂM: ĐẠT` |

Mã thoát: 0 ổn · 1 lỗi đọc tệp · 2 dữ liệu cũ quá 2 ngày (kết luận hàng đồng không đáng tin).

Nhớ:
- Giá trị tính theo **giá lẻ công khai**, chỉ là ước tính, không phải giá vốn.
- SIM không tính giá trị.
- Thấy cảnh báo `du-lieu-cu` thì kiểm job cập nhật sheet trước, chưa kết luận hàng đồng.
