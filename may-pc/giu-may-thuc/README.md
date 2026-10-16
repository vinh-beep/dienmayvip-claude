# Giữ máy PC thức (không Sleep) để phiên Claude Remote Control không rớt

Bấm đúp `Giu-May-Thuc.bat` → bấm **Yes** khi Windows hỏi quyền Admin. Chạy lại nhiều lần cũng được.

Làm gì:
1. Sao lưu sơ đồ nguồn điện hiện tại (`SaoLuu-NguonDien.pow`) — chỉ lần đầu.
2. Khi cắm điện: Sleep = Never, Hibernate = Never, tắt "ngủ tự động ẩn", tắt USB selective suspend. Màn hình vẫn tắt sau 15 phút (không ảnh hưởng phiên).
3. Card mạng: không cho Windows tắt để tiết kiệm điện.
4. Windows Update: giờ hoạt động 06h–23h, không tự khởi động lại trong khung này.
5. Ghi log `Giu May Thuc Result <dd MM yyyy HHhmmp>.txt`, kèm danh sách Sleep / khởi động lại / mất điện 14 ngày qua để biết vì sao phiên rớt.

Khôi phục cài đặt cũ: bấm đúp `Khoi-Phuc-Nguon-Dien.bat`.

Giới hạn: không chặn được mất điện, rớt mạng do modem, hay khởi động lại ngoài giờ 06h–23h. Sau khi máy khởi động lại vẫn phải mở lại Claude Desktop / `claude remote-control`.
