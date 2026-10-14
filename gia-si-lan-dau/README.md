# Ghi lô giá sỉ lần đầu vào HTsoft

Ghi lô giá sỉ lần đầu (278 mã sạch, loại 27 mã nghi ghép nhầm) vào `dmv_GiaSi` và `MATHANG.GIABANBUON`.
Chạy trên máy Windows có nối SQL Server 192.168.1.200 (cần Python + `pyodbc` + `openpyxl`, giống engine giá).

## Cách chạy (Explorer → Ctrl+L → dán đường dẫn .bat → Enter)

1. Chép thư mục này vào `C:\Users\Win10\Desktop\Parent SKU\AutoSync\gia-si-lan-dau\`.
2. `CHAY_01_KHAM_PHA.bat` — CHỈ ĐỌC. In tiêu đề file lô và tên cột thật của `MATHANG`, `dmv_GiaSi`, `dmv_Rule_Gia` ra log.
   Đối chiếu với `config.json`; chỗ nào tên cột khác thì sửa (nhất là `mathang.cot_gia_le` và mục `dmv_gisi`).
3. `CHAY_02_GHI_LO.bat` — chạy XEM TRƯỚC (không ghi), nếu qua hết mới chuyển sang GHI THẬT và hỏi gõ đúng chữ `GHI`.
4. Đọc log trong `thu_muc_log` và file `Ket Qua Ghi Lo Gia Si Lan Dau dd MM yyyy HHhmmp.xlsx` trên Desktop\Parent SKU.

## Chốt an toàn (script tự dừng, chưa ghi gì, nếu vi phạm)

- Số mã sạch sau lọc phải ĐÚNG BẰNG `lo.so_ma_mong_doi` (278).
- Lọc theo cột "Lãi trên vốn" trong file lô: > `lai_toi_da` (10%) hoặc ≤ 0 thì loại; mã trùng, giá trống thì loại.
- Mọi tên cột trong config được kiểm tra có thật trong DB trước khi chạm dữ liệu.
- Tại DB: mã phải có trong MATHANG, giá sỉ phải < giá lẻ hiện tại.
- Backup trước: `bak_MATHANG_GIABANBUON_<yyyymmdd>` (chỉ các mã trong lô) và `bak_dmv_GiaSi_<yyyymmdd>` (cả bảng).
- Một TRANSACTION; số dòng ghi vượt lô hoặc sau ghi còn lệch thì ROLLBACK.
- Idempotent: chạy lại chỉ sửa dòng còn lệch, không ghi trùng.

## Khôi phục nếu cần

```sql
UPDATE m SET m.GIABANBUON = b.GIABANBUON
FROM dbo.MATHANG m JOIN dbo.bak_MATHANG_GIABANBUON_<yyyymmdd> b ON b.MA = m.MHCODE;
```
