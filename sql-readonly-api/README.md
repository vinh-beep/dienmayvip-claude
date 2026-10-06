# DMV API chỉ-đọc cho SQL Server

API nhỏ chạy **trên máy SQL Server**, để Claude Cloud đọc tồn và giá bán qua HTTPS.

## Nguyên tắc: 0 token, không lỗi giới hạn

- API và mọi xử lý định kỳ là **mã Python thuần**, không gọi AI nào → không tốn token API, không dính giới hạn.
- Claude chỉ đọc kết quả khi anh cần phân tích. Trang mặc định chỉ **50 dòng**, tối đa theo `max_rows` của từng view, nên mỗi lần đọc rất nhẹ.
- Việc nặng (chấm điểm, so giá, xuất báo cáo) chạy bằng script trên máy hoặc lịch của Windows. Claude chỉ đọc kết quả đã tính.

## An toàn

- Không có SQL tùy ý. Chỉ đọc các view liệt kê trong `views.json`, tên view phải bắt đầu `vw_API_`.
- Cột nghi là giá vốn, giá nhập, NCC, mật khẩu, token, SĐT, email bị chặn ngay khi khởi động.
- Giá trị lọc luôn đi qua tham số `?`. Chỉ lọc được cột khai trong `filter_columns`.
- Token Bearer ≥ 32 ký tự. Sai 10 lần trong 5 phút thì khóa IP tạm. Mặc định 120 lượt/phút.
- API **từ chối khởi động** nếu login SQL có quyền sysadmin, db_owner, db_datawriter hoặc db_ddladmin.
- Lỗi SQL không trả chi tiết ra ngoài. Nhật ký `api-audit.log` ghi view, số dòng, tên cột lọc; không ghi giá trị dữ liệu hay token.
- Không có trang `/docs`. Chỉ `/health` không cần token và không trả dữ liệu.

## Cài đặt trên máy SQL Server

1. Cài Python 3.11+ và ODBC Driver 17 hoặc 18 for SQL Server.
2. `pip install -r requirements.txt`
3. Tạo các view `vw_API_...` chỉ chứa cột bán hàng (không giá vốn, giá nhập, NCC, SĐT). Tên cột theo tài liệu MATHANG Section 29, không đoán.
4. Tạo login chỉ-đọc theo `cap-quyen.sql.example`.
5. Sao chép `views.example.json` thành `views.json` rồi sửa cho khớp view thật.
6. Sao chép `config.env.example` thành `config.env`, điền thông tin. Tạo token:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
7. Chạy thử:
   `uvicorn app:create_app_from_env --factory --host 127.0.0.1 --port 8765`
8. Thử trên máy:
   `curl -H "Authorization: Bearer <token>" http://127.0.0.1:8765/v1/views`

API chỉ nghe `127.0.0.1`. Kết nối SQL dùng `Encrypt=no;TrustServerCertificate=yes` như các app hiện tại.

## Mở ra cho Cloud bằng Tailscale Funnel

1. Trong trang quản trị Tailscale: bật HTTPS Certificates và cho phép Funnel cho máy `dienmayvip2023`.
2. Trên máy SQL: `tailscale funnel --bg 8765`. Lệnh in ra địa chỉ `https://dienmayvip2023.<tên>.ts.net`.
3. Trong cài đặt môi trường Cloud (menu môi trường ở thanh tiêu đề → Edit → Network access), thêm tên miền đó vào **Allowed domains**.
4. Gọi từ Cloud: `GET https://<địa chỉ>/v1/views/ton-gia-ban?limit=50` kèm header `Authorization: Bearer <token>`.
5. Muốn tắt ngay: `tailscale funnel reset`.

Funnel là địa chỉ **công khai**, nên bắt buộc dùng token mạnh và login chỉ-đọc như trên. Không dán token vào chat, kho GitHub hay file chia sẻ; hãy đưa token cho Claude qua cách an toàn khác.

## Chạy nền

Dùng NSSM đăng ký dịch vụ chạy lệnh ở bước 7, thư mục làm việc là thư mục này, tự khởi động lại khi lỗi.

## Kiểm thử

`pip install pytest httpx` rồi `python -m pytest -q` (42 ca, dùng SQLite giả lập, không cần SQL Server).

Phần chưa thử: kết nối SQL Server thật và Funnel thật. Cần thử trên máy của anh trước khi dùng.
