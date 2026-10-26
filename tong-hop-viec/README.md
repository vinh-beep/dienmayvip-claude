# Tổng hợp việc từ mọi app (kiểu Lark Mail) — 0 token

Gom việc gấp / đang làm / chờ anh mà Chuông VIP và các app `.exe`, Python, `.cmd` đã ghi rải rác (tin JSON trên Bridge, `ket-qua-*`, ghi chú `.md` có frontmatter), rồi tổng kết theo danh mục. Mã thuần, không gọi API nào, nên không chết vì lỗi quyền API như trợ lý nền ngày 26/10.

```
python tong_hop_viec.py --nguon "G:\My Drive\DMV-Cloud-Bridge" --nguon "D:\Obsidian Vault DMV\03 Viec" --ra "C:\AIVIP\state\tong-hop-viec"
python tong_hop_viec_ui.py --nguon ... --ra ...        # giao diện: danh mục trái, nội dung phải, 📋 Chép tất cả
```

## Cách xếp
- **Trạng thái** từ tiêu đề và nội dung: 🔴 gấp (KHẨN, báo động) · ⏳ chờ anh · 🕳 treo (tin gửi quá `--treo-gio`, mặc định 6 giờ, chưa có `ket-qua`) · ⚠ cảnh báo · 🟡 đang làm · ✅ xong. Tin có `ket-qua` cùng `chu_de` tự thành xong. Ghi chú `loai: tri-thuc` không tính là việc mở.
- **Danh mục**: theo tag `chủ-đề/...` trước, không có thì theo từ khoá: Tài chính · Giá/BG · Tồn kho · Video/MXH/Nhạc · Hộp mail/Chuông · AI/Hạ tầng/App · Khác.
- Thư mục `_done` bị bỏ qua.

## Tệp ra
- `tong-hop-<ngày>.md`: khối 🔥 cần xử lý ngay, rồi từng danh mục; cuối tệp có khối **📋 CHÉP TẤT CẢ**.
- `chep-tat-ca.txt`: bản gọn chỉ việc còn mở, để dán cho AI tổng hợp (Claude/Gemini) hoặc Chuông.
- `tong-hop-<ngày>.json`, và `tong-hop-index.md` liên kết mọi bản tổng hợp theo ngày.

## An toàn
Mọi tiêu đề và tóm tắt đều qua bước che: SĐT, số tài khoản thành `[che: ...]`; dòng có giá vốn / giá nhập / NCC rẻ nhất bị thay bằng `[che: dòng có giá nội bộ]`. Tự kiểm đột biến xác nhận tắt bước che là bộ kiểm đỏ.

## Gợi ý lịch
Task Scheduler mỗi 30 phút chạy `tong_hop_viec.py`; Chuông VIP đọc `chep-tat-ca.txt` để hiện "N việc cần chú ý". Khi cần AI tổng hợp sâu, dán `chep-tat-ca.txt` vào phiên Claude (1 lần, ít token) thay vì cho AI đọc từng ghi chú.

Kiểm thử: `python -m pytest -q` (18 ca logic + 1 ca giao diện, tự bỏ qua khi không có Tkinter).
