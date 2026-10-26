# dienmayvip-claude

Mã nguồn Claude Cloud dựng cho hệ thống DienmayVIP.

- `sql-readonly-api/` — API chỉ-đọc cho SQL Server (xem README trong thư mục).
- `video-links/` — bảng link video YouTube/TikTok, nút Mở tệp trong thư mục, thanh % tiến độ (xem README trong thư mục).
- `ton-dong/` — kiểm tra tồn đọng thật từ sheet tổng hợp (xem README trong thư mục).
- `drive-sync/` — đồng bộ thư mục chọn lọc lên Google Drive bằng rclone, có quét an toàn (xem README trong thư mục).
- `doi-chieu-ton/` — Excel mẫu đối chiếu tồn Shopee với HTSoft (Kho VV + Kho 30LL).
- `qr-cua-hang/` — QR tại cửa hàng: xem giá/tồn, gọi tư vấn tại kệ, đăng ký bảo hành, đo hiệu quả ấn phẩm.
- `may-pc/giu-may-thuc/` — bấm đúp để giữ máy PC không Sleep, phiên Remote Control không rớt.
- `CLAUDE.md` — giao thức cầu nối Drive Bridge cho mọi phiên Claude Cloud và PC.

## Kiểm thử

- `python kiem_tat_ca.py`: chạy bộ kiểm của từng thư mục, báo bảng kết quả.
- `python kiem_tat_ca.py --tu-kiem`: kiểm tra chính bộ kiểm. Cố ý phá 18 chỗ quan trọng (tắt xác thực, tắt chặn cột giá vốn, đổi `copy` thành `sync`...), bộ kiểm phải báo đỏ.
- CI (`.github/workflows/tests.yml`) chạy cả hai trên Ubuntu và Windows mỗi lần đẩy mã.

Kho này **công khai**: không đưa giá vốn, giá NCC, mật khẩu, token, chuỗi kết nối hay số điện thoại lên đây.
