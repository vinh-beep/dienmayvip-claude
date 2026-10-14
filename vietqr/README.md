# VietQR Phiếu Thu — DienmayVIP

Tạo QR chuyển khoản **offline** (không qua SePay hay web nào) từ phiếu bán trong HTsoft, hoặc nhập tay.

QR đúng chuẩn Napas 247 / VietQR. Đã đối chiếu với 2 QR do SePay sinh: chuỗi trùng từng ký tự, kể cả nội dung CK.

## Dùng

- **Trái:** danh sách phiếu bán 30 ngày gần nhất. Tìm theo số phiếu hoặc tên khách.
- **Giữa:** chọn ngân hàng nhận (mặc định ACB). Khách, sản phẩm, số tiền tự điền từ phiếu và sửa được (ví dụ thu cọc một phần).
  Nội dung CK tự ghép: `TEN KHACH thanh toan tien hang <SP> <SOTIEN>`, tự bỏ dấu, tối đa 95 ký tự (tự rút gọn tên SP).
- **Phải:** QR xem trước. Lưu PNG / Chép ảnh (dán thẳng vào Zalo) / In / Mở thư mục.
- Mỗi QR lưu vào `out/don-hang/` kèm dòng nhật ký `nhat-ky.csv`. Thư mục này có tên khách nên **không** đưa lên GitHub.

Chưa cấu hình SQL hoặc mất kết nối: app vẫn chạy, nhập tay ở khung giữa.

## Cài trên máy Windows

1. Chép thư mục `vietqr` về máy, ví dụ `C:\Service\VIETQR DIENMAYVIP\`.
2. Chạy `build_exe.bat`. Lệnh này cài thư viện, đóng gói `.exe` và tự kiểm. File nằm trong `dist\`.
3. Nối SQL (tùy chọn, chỉ đọc):
   - Chạy `do_cot.sql` trong SSMS để lấy tên cột thật của `BANHOADON` / `BANCTHOADON`.
   - Sao chép `phieu_ban.config.example.json` thành `phieu_ban.config.json`, điền server, database và các cột còn trống
     (mã khách, tổng tiền, khóa nối chi tiết, tên hàng của MATHANG theo Section 29). Không đoán tên cột.
   - Đặt `phieu_ban.config.json` cạnh file `.exe` rồi mở lại app.

App chỉ chạy câu `SELECT` có hình dạng cố định; tên bảng/cột trong cấu hình phải qua kiểm tra, giá trị tìm kiếm đi qua tham số.

## Thêm ngân hàng

Thêm một dòng vào `accounts.json`: `code`, `bank`, `bin` (mã Napas 6 số), `stk`, `name`. Ví dụ Vietcombank `970436`.
`python vietqr_gen.py` tạo lại QR tĩnh để in đặt quầy (`out/`).

## Kiểm thử

`pip install pytest qrcode pillow` rồi `python -m pytest -q tests` (14 ca, không cần SQL Server).
