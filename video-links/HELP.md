# video-links — Trợ giúp nhanh (F1)

Bảng link video YouTube / TikTok, mở tệp trong thư mục, thanh % đã đăng. Chi tiết: `README.md`.

| Việc | Lệnh / phím |
|---|---|
| Mở giao diện | `python video_links_ui.py so_video.json` |
| In bảng tổng kết | `python video_links.py so_video.json` |
| Tự kiểm (không cần tệp) | `python video_links.py --kiem` → phải in `KIỂM: ĐẠT` |
| Mở tệp trong thư mục | chọn dòng → Ctrl+O, nhấp đúp hoặc Enter |
| Mở link | chọn dòng → Ctrl+L |
| Lọc nền tảng | menu Xem → Tất cả / YouTube / TikTok |

Nhớ:
- Chỉ link `http/https` được mở. Link `javascript:`, `file:` bị bỏ.
- Đường dẫn tệp có dấu `"` hoặc xuống dòng bị từ chối. App không bao giờ chạy tệp, chỉ hiện tệp trong Explorer.
- Tệp đã mất thì app mở thư mục chứa nó.
