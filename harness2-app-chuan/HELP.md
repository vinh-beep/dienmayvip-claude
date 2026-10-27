# harness2-app-chuan — Trợ giúp nhanh (F1)

Chấm mọi thư mục app theo chuẩn Harness² (tự kiểm, trợ giúp, không bí mật gán cứng...). Chỉ đọc, không sửa app. Chi tiết: `README.md`.

| Việc | Lệnh |
|---|---|
| Chấm các app | `python kiem_chuan_app.py --goc "C:\Service" --goc "C:\ClaudeVIP" --ra ket-qua` |
| Đổi mục bắt buộc | thêm `--bat-buoc kiem,help,bi-mat` |
| Kiểm chính bộ chấm | `python -m pytest -q` trong thư mục này |

Mã thoát: 0 mọi app đạt mục bắt buộc · 1 có app hỏng.

Mục bắt buộc mặc định: `kiem` (có lệnh `--kiem`), `help` (có `HELP.md`), `bi-mat` (không khoá/mật khẩu gán cứng).

Nhớ: mục `kiem` chỉ dò chữ `--kiem` trong thư mục. Khi vá app, làm lệnh `--kiem` thật chạy được, đừng chỉ ghi chữ vào tài liệu.
