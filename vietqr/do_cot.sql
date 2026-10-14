-- CHỈ ĐỌC. Chạy trong SSMS trên DB HTsoft để tìm tên cột cho phieu_ban.config.json.
-- 1) Cột của bảng phiếu bán, chi tiết phiếu bán (cần: mã khách, tổng tiền, khóa nối chi tiết).
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('BANHOADON', 'BANCTHOADON')
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- 2) Bảng có thể là "phiếu thu" (nếu anh muốn lấy từ phiếu thu thay vì phiếu bán).
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME LIKE '%THU%' ORDER BY TABLE_NAME;

-- 3) Tên cột tên hàng của MATHANG: xem tài liệu MATHANG Section 29 (không đoán).
