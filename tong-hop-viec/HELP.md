# tong-hop-viec — Trợ giúp nhanh (F1)

Gom việc gấp / chờ anh / treo từ mọi app rồi tổng kết theo danh mục, có nút Chép tất cả. Chi tiết: `README.md`.

| Việc | Lệnh |
|---|---|
| Chạy | `python tong_hop_viec.py --nguon "G:\My Drive\DMV-Cloud-Bridge" --ra ket-qua` |
| Mở giao diện | `python tong_hop_viec_ui.py --nguon ... --ra ...` |
| Đổi ngưỡng treo | thêm `--treo-gio 4` (mặc định 6 giờ) |
| Chỉ lấy từ ngày | thêm `--tu-ngay 2026-10-25` |
| Tự kiểm (không đọc Bridge thật) | `python tong_hop_viec.py --kiem` → phải in `KIỂM: ĐẠT` |

Tệp ra: `tong-hop-<ngày>.md`, `chep-tat-ca.txt` (dán cho AI hoặc Chuông), `tong-hop-<ngày>.json`, `tong-hop-index.md`.

Nhớ:
- SĐT, số tài khoản và dòng có giá vốn / giá nhập / NCC rẻ đều bị che trước khi ghi.
- Tin gửi quá ngưỡng mà chưa có `ket-qua` cùng chủ đề thì thành "treo".
