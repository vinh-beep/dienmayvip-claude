# sql-readonly-api — Trợ giúp nhanh (F1)

API chỉ-đọc cho SQL Server: Claude Cloud đọc tồn và giá bán qua HTTPS, không bao giờ ghi. Chi tiết: `README.md`.

| Việc | Lệnh |
|---|---|
| Tự kiểm rào chắn (không cần cấu hình, không SQL) | `python kiem_ket_noi.py --kiem` → phải in `KIỂM: ĐẠT` |
| Kiểm cấu hình + views.json (không đụng SQL) | `python kiem_ket_noi.py --nhe` |
| Kiểm đầy đủ trước khi mở ra ngoài | `python kiem_ket_noi.py` |
| Chạy API trên máy | `uvicorn app:create_app_from_env --factory --host 127.0.0.1 --port 8765` |
| Thử gọi | `curl -H "Authorization: Bearer <token>" http://127.0.0.1:8765/v1/views` |
| Tắt mở ra ngoài ngay | `tailscale funnel reset` |

Mã thoát `kiem_ket_noi.py`: 0 đạt · 1 có mục hỏng (khi đó KHÔNG mở ra ngoài).

Nhớ:
- Chỉ đọc view tên bắt đầu `vw_API_`. Cột nghi giá vốn, NCC, SĐT, mật khẩu, token bị chặn ngay khi khởi động.
- Login SQL có quyền ghi hoặc quản trị thì API từ chối chạy.
- Không dán token vào chat, GitHub hay tệp chia sẻ.
