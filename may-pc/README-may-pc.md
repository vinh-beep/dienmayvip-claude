# Bộ chạy trên máy PC / máy SQL Server (bấm đúp, tự xin quyền Admin)

| Thư mục | Tệp bấm đúp | Làm gì |
|---|---|---|
| `giu-may-thuc/` | `Giu-May-Thuc.bat` | Không Sleep khi cắm điện, giữ card mạng, Windows Update không tự khởi động lại 06h–23h. Có tệp khôi phục. |
| `suc-khoe/` | `Bao-Cao-Suc-Khoe.bat` | Báo cáo CPU, RAM, bộ nhớ cam kết, số tiến trình Claude/node, phiên Remote Control, SQL Server → `ket-qua-PC-SUC-KHOE-<tên máy>-moi-nhat.md` trên Bridge; lặp mỗi 30 phút. Chạy trên **cả PC và máy SQL Server**. Chỉ đọc. |
| `giu-phien-rc/` | `Giu-Phien-RC.bat` | Khi đăng nhập Windows: tự mở lại tối đa 5 phiên `claude remote-control` theo `thu-muc-phien.txt`; phiên tắt thì 60 giây sau tự mở lại. |

Chưa chạy thử trên Windows thật (Cloud không có Windows). Đọc log/tệp kết quả sau lần chạy đầu.
