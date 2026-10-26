# Áp Harness² vào TẤT CẢ app (.exe · Python · cmd) — bảng kiểm từng app

Anh Vĩnh duyệt 26/10/2026: áp Harness² vào mọi app. Mỗi app đi qua bảng này; **đạt đủ 10 ô mới được gắn nhãn "H2-ĐẠT"**. Phiên PC-Service giữ bảng trạng thái tại `C:\ClaudeVIP\harness2\ap-dung-app.json`.

## Bảng kiểm (mỗi app 1 dòng)
| # | Ô kiểm | Cách làm | Luật |
|---|---|---|---|
| 1 | Có `--kiem` (hoặc `/kiem`) chạy không cần SQL/mạng, thoát 0 khi ổn | Thêm cờ vào `main`; app .exe đóng gói từ Python thì giữ cùng cờ | H8 |
| 2 | Mỗi lượt chạy ghi `ket-qua-PC-H2-<app>-<giờ>.md` (bắt đầu/xong/lỗi + mã thoát) | Dùng `ghi_ket_qua()` trong `chay_bu.py` hoặc viết tương đương | H1 |
| 3 | "XONG" kèm **số đọc lại từ đích** (số dòng, md5, số bản ghi) | Ghi vào tệp H1 dòng `- Đọc lại: …` | luật 26/10 |
| 4 | Khi xong ghi `{"<app>": {"xong": "<ISO>"}}` vào `trang-thai-h2.json` | Để chạy bù không chạy lại việc đã xong | H2 |
| 5 | Kiểm quyền trước khi chạy (Gmail/Drive/SQL); hỏng → 1 báo cáo gộp, thoát mã 2 | Khai lệnh kiểm trong `chay_bu.config.json` → `kiem_quyen` | H5 |
| 6 | 0 kết quả 3 lần liên tiếp → tự báo cảnh báo dù mã thoát 0 | Đếm trong trang-thai-h2.json; quá 3 → ghi tin `__tin__` cảnh báo | H11 |
| 7 | Không mở cửa sổ console; chạy tuần tự | `pythonw` hoặc `CREATE_NO_WINDOW`; một tiến trình mỗi lúc | H10 |
| 8 | Có cửa RAM: thiếu thì hoãn, không ép | Khai `can_ram_mb` trong cấu hình; app nạp mô hình AI bắt buộc | H3 |
| 9 | Việc tiền/ngân hàng: `nhom: "tien"`, không bao giờ tự chạy bù | LENH-BANK, sổ phụ, thanh toán, chuyển khoản | H2 |
| 10 | Gặp lỗi cấp tổ chức/tài khoản (disabled subscription, invalid_grant) → dừng, báo 1 tin, không thử lại liên tục | Bắt chuỗi lỗi, ghi tin, thoát mã 2 | H15 |

## Danh sách app phải đi qua (PC-Service điền trạng thái)
Chuông VIP · Lark Mail VIP.exe · Hộp Mail VIP · Thông Báo VIP · DMV ChatAI Service · DMV DongBo Service · DMV Canh Khoa Clipboard · DMV Canh Phat Sinh HTsoft · DMV Email Phan Loai / Noi Viec / Can Xu Ly · Theo Doi Gia Shopee · Gia AI Chot · Hoc Gia San · M1 tồn kho · Day Viec Ton Len Drive · Nhạc DienmayVIP.exe (mới) · mọi tác vụ trong Task Scheduler có tiền tố DMV.

## Thứ tự làm
1. App nào đang **lỗi** trong bản tin trạng thái → làm trước (hiện: 5 tác vụ email, DongBo Service, ChatAI Service).
2. App chạy **theo lịch** → kế tiếp (để chạy bù có tác dụng).
3. App chạy tay → sau cùng.

Mỗi app xong, PC-Service ghi 1 dòng vào `ket-qua-PC-H2-AP-DUNG-<giờ>.md`: tên app · số ô đạt /10 · ô còn thiếu. Tổng kết tự động (`tong-ket-bridge`) sẽ gom các dòng này.
