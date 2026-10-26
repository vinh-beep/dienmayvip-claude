# Harness² — chạy bù việc bị lỡ

Anh Vĩnh duyệt ngày 25/10/2026: Harness² **tự chạy bù việc bị lỡ khi máy bật lại, TRỪ việc ngân hàng/tiền**.

Đây là mã Python thuần, chỉ dùng thư viện chuẩn, không gọi AI (0 token). Harness² gọi nó **một lần lúc khởi động**. Mã này không tự đặt lịch và không tạo scheduled task.

## Luật
| Mã | Luật |
|---|---|
| H1 | Mỗi việc ghi `ket-qua-PC-H2-<việc>-<giờ>.md` lên Bridge, ghi bắt đầu / xong / lỗi kèm mã thoát. Không ghi nội dung đầu ra, để không lộ giá hay PII. |
| H2 | Giờ lịch đã qua trong **12 giờ** (đổi được theo từng việc qua `cua_so_gio`) mà chưa có "xong" sau giờ đó → chạy bù. Quá cửa sổ thì chỉ báo. |
| Tiền | Việc thuộc `nhom: "tien"`, hoặc tên có BANK / NGÂN HÀNG / SỔ PHỤ / THANH TOÁN / CHUYỂN KHOẢN / TÀI CHÍNH → **không bao giờ tự chạy**, chỉ báo anh. |
| H3 | RAM trống nhỏ hơn `can_ram_mb` cộng 1 GB dự phòng → hoãn, không ép nạp. |
| H5 | Kiểm quyền (Gmail/SQL…) mỗi loại **1 lần**. Hỏng quyền → gom các việc liên quan vào 1 báo cáo, không chạy. |
| H10 | Chạy tuần tự, một tiến trình mỗi lúc, `CREATE_NO_WINDOW`. Máy chính từng treo vì cạn heap desktop do quá nhiều cửa sổ console. |

## Cách dùng trên PC
1. Chép thư mục này vào `C:\ClaudeVIP\harness2\chay-bu`. Sao `chay_bu.config.example.json` thành `chay_bu.config.json`, rồi sửa lệnh và giờ theo lịch thật.
2. Chạy thử, chỉ in kế hoạch: `python chay_bu.py --config chay_bu.config.json`
3. Chạy thật: thêm `--chay-that`. Gắn lệnh này vào bước khởi động **có sẵn** của Harness².
4. Mã thoát: `0` ổn · `1` có việc lỗi · `2` có việc chờ anh (tiền, quá cửa sổ, hỏng quyền, hoãn RAM). Khi mã là 1 hoặc 2, tệp `ket-qua-PC-H2-CHAY-BU-<giờ>.md` được ghi lên Bridge.
5. Khi lịch gốc chạy xong một việc, Harness² cũng phải ghi `{"<việc>": {"xong": "<ISO giờ VN>"}}` vào `trang-thai-h2.json`. Nếu không ghi, lần khởi động sau sẽ tưởng việc đó bị lỡ.

## Kiểm thử
`python test_chay_bu.py`: 16 ca kiểm thử. Có ca dựng lại đúng lần rớt máy 25/10 (05h53 → 13h46): LENH-BANK chỉ báo, không chạy; M1 và bản tin được chạy bù.
