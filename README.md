# dienmayvip-claude

Mã nguồn Claude Cloud dựng cho hệ thống DienmayVIP.

- `sql-readonly-api/` — API chỉ-đọc cho SQL Server (xem README trong thư mục).
- `drive-sync/` — đồng bộ thư mục chọn lọc lên Google Drive bằng rclone, có quét an toàn và Harness² vòng 2 cho bộ chặn (xem README trong thư mục).
- `HARNESS2.md` — luật Harness² (vòng 1 dự đoán → vòng 2 đo thật → sổ bài học) và cách từng module trong kho áp dụng.

## Kiểm thử

- `python kiem_tat_ca.py`: chạy bộ kiểm của từng thư mục, báo bảng kết quả.
- `python kiem_tat_ca.py --tu-kiem`: kiểm tra chính bộ kiểm. Cố ý phá 15 chỗ quan trọng (tắt xác thực, tắt chặn cột giá vốn, đổi `copy` thành `sync`...), bộ kiểm phải báo đỏ.
- CI (`.github/workflows/tests.yml`) chạy cả hai trên Ubuntu và Windows mỗi lần đẩy mã.

Kho này **công khai**: không đưa giá vốn, giá NCC, mật khẩu, token, chuỗi kết nối hay số điện thoại lên đây.
