# Bộ chạy trên máy PC / máy SQL Server (bấm đúp, tự xin quyền Admin)

| Thư mục | Tệp bấm đúp | Làm gì |
|---|---|---|
| `giu-may-thuc/` | `Giu-May-Thuc.bat` | Không Sleep khi cắm điện, giữ card mạng, Windows Update không tự khởi động lại 06h–23h. Có tệp khôi phục. |
| `suc-khoe/` | `Bao-Cao-Suc-Khoe.bat` | Báo cáo CPU, RAM, bộ nhớ cam kết, số tiến trình Claude/node, phiên Remote Control, SQL Server → `ket-qua-PC-SUC-KHOE-<tên máy>-moi-nhat.md` trên Bridge; lặp mỗi 30 phút. Chạy trên **cả PC và máy SQL Server**. Chỉ đọc. |
| `giu-phien-rc/` | `Giu-Phien-RC.bat` | Giữ tối đa 5 phiên `claude remote-control` theo `thu-muc-phien.txt`. Canh gác mỗi 5 phút và khi đăng nhập; mất mạng thì đợi có mạng mới mở; chặn Windows Update tự khởi động lại khi đang đăng nhập; phiên tắt nhanh 3 lần (hết hạn đăng nhập) thì báo lên Bridge + bật hộp thoại. Gỡ: `Go-Giu-Phien-RC.bat`. |
| `giu-mods/` | `Giu-Mods.bat` | Chép mọi Claude Mod (đang nằm riêng trong từng phiên) vào `~/.claude/mods-co-dinh` và ghi `CLAUDE_CODE_PLUGIN_DIRS` vào `settings.json`, để phiên mở lại vẫn có mod. Gỡ: `Go-Giu-Mods.bat`. |
| `tim-loi-rc/` | `Tim-Loi-RC.bat` | Chỉ đọc: tìm tác vụ/sự kiện Windows gây rớt Remote Control quanh 00h/12h, ghi lên Bridge. |

Chưa chạy thử trên Windows thật (Cloud không có Windows). Đọc log/tệp kết quả sau lần chạy đầu.
