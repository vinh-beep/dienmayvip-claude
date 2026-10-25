# Đồng bộ thư mục chọn lọc lên Google Drive (rclone, 0 token)

Mã Python thuần chạy trên PC, không gọi AI nào. Mặc định **chạy thử**, chỉ ghi lên Drive khi có `--chay-that`.

## Cách hoạt động

1. `kiem_an_toan.py` đi qua các thư mục anh chọn trong cấu hình, bỏ `venv`, `site-packages`, `torch`, `node_modules`, `.git`, `__pycache__`, `_Config`, `~$*`, `*.tmp`, `*.pyc`, `*.log`, mọi `*.bak*`; bỏ tệp quá `max_size` (50M), cũ hơn `max_age` (2d) hoặc đang ghi dở (`min_age`, 1m); bỏ qua liên kết thư mục.
2. **Chặn theo tên:** `*.env`, `*.pem`, `*.key`, `*token*`, `*secret*`, `*password*`, `*tkxt*`, `*giavon*`, `*gianhap*`, `gmail_imap.txt`...
3. **Chặn theo nội dung:** khóa API, token, mật khẩu, khóa riêng, số điện thoại VN, số tài khoản, CCCD, và các cột giá vốn, NCC rẻ nhất, giá gợi ý VIP trong tệp dữ liệu (`json/csv/md/txt/xml/html`, trong `xlsx/docx/pptx`). Mã nguồn (`.py/.ps1/.sql...`) chỉ bị chặn khi chứa bí mật thật, không chặn vì có tên cột.
4. **Tệp không quét được** (PDF, zip, `.db`, loại lạ) bị chặn mặc định. Ảnh/video đi qua. Muốn cho một loại đi qua thì thêm vào `cho_phep_duoi_khong_quet`, ví dụ `[".pdf"]`.
5. Danh sách tệp đã duyệt đưa cho `rclone copy --files-from`. Chỉ `copy`: thêm và cập nhật, **không xóa** gì trên Drive (tệp đổi thì Drive giữ bản cũ trong lịch sử phiên bản).
6. Log nằm ở `thu_muc_log`: `trang-thai-dong-bo.json`, `chan-<giờ>.txt` (tệp nào bị chặn bởi luật nào, **không ghi nội dung khớp**), `rclone-<tên>-<giờ>.log`.
7. Sau lần đẩy thật thành công, `trang-thai-dong-bo.json` được đẩy lên Drive để Claude đọc nhanh (rất ít token).
8. `--kiem-tuoi`: nếu quá `bao_loi_sau_gio` (24) chưa đẩy được, ghi một tin `tin-...__viec__dong-bo-drive-loi.json` vào thư mục Bridge cho phiên trực (tối đa 1 tin mỗi 24 giờ) và thoát mã 2.

## Cài đặt trên PC

1. Cài [rclone](https://rclone.org/downloads/) và Python 3.11+.
2. **Google Cloud:** tạo project → bật Google Drive API → màn hình OAuth consent → tạo OAuth client (Desktop app).
   - Nếu để trạng thái *Testing*, token đăng nhập hết hạn sau **7 ngày** và đồng bộ sẽ tự dừng. Với `beseebest@gmail.com` hãy chuyển sang *In production* (dùng cá nhân, bỏ qua cảnh báo chưa xác minh). Với tài khoản Workspace `vinh@dienmayvip.com` chọn loại *Internal*.
3. `rclone config` → New remote tên `dmv-drive`, type `drive`, nhập Client ID/Secret của anh, scope `drive`, **root_folder_id = id thư mục DMV-Cloud-Bridge**. Tài khoản `beseebest@` cần remote riêng (ví dụ `dmv-drive-b:`) và một bản cấu hình riêng, hoặc chia sẻ thư mục cho tài khoản đó. Không dán Client Secret vào chat hay GitHub.
4. Chép thư mục này vào `C:\DMV_DongBoDrive`, sao chép `dong_bo.config.example.json` thành `dong_bo.config.json` rồi sửa: điền thư mục xuất báo cáo thật vào chỗ `<THU-MUC-XUAT-BAO-CAO>`.
5. **Chạy thử:** `python dong_bo_drive.py --config dong_bo.config.json`. Đọc `chan-*.txt` và `files-from-*.txt` trong thư mục log, xem rclone `--dry-run` định đẩy gì.
6. **Chạy thật lần đầu:** thêm `--chay-that`.
7. **Đặt lịch:** `powershell -ExecutionPolicy Bypass -File dat_lich.ps1` (chỉ in lệnh), rồi thêm `-XacNhan` để đăng ký 2 tác vụ: đẩy lúc 02:30 mỗi ngày và kiểm quá hạn mỗi 6 giờ. Mỗi tác vụ ghi log riêng.

## Harness² vòng 2 — bộ chặn tự học từ phán xử của anh (`hoc_tu_chan.py`)

Bộ quét ở trên là **vòng 1**: đoán "tệp này nguy hiểm" rồi chặn. Theo luật Harness² (25/10/2026), mọi vòng tự động có điểm dự đoán phải có **vòng 2 đo kết quả thật**. Với chốt chặn, kết quả thật là **bao nhiêu lần báo oan**.

1. Sau mỗi lượt đồng bộ, mở `so-bai-hoc-chan.md` trong thư mục log, mục ⑤ liệt kê tệp bị chặn chờ anh phán xử.
2. Phán xử: `python hoc_tu_chan.py --config dong_bo.config.json --phan-xu "BaoCao/bang.pdf=oan" "BaoCao/kh.csv=dung"`.
   `oan` = tệp lành bị chặn nhầm; `dung` = chặn đúng. Phán xử ghi vào `phan-xu-chan.json` (chỉ thêm/ghi đè theo tệp, không xoá).
3. Lệnh trên tính lại sổ: `bai-hoc-chan.json` (máy đọc) và `so-bai-hoc-chan.md` (người đọc, mới nhất trên cùng, sinh lại cả tệp mỗi lượt nên không nhân đôi). Chạy không kèm `--phan-xu` chỉ để tính lại sổ.
4. Lượt đồng bộ kế tiếp đọc `bai-hoc-chan.json`: tệp anh đã phán **oan** được đi qua **chỉ khi** nội dung còn y nguyên (so SHA-256 ghi lúc phán xử). Đổi nội dung → chặn lại từ đầu. Trạng thái ghi thêm cột `theo_bai_hoc`.

Luật cứng và luật mềm:

| Loại | Luật | Phán "oan" có tác dụng? |
|---|---|---|
| **Cứng** | mọi luật bí mật (khoá API, token, khoá riêng, JWT, gán mật khẩu), `gia-von-ncc`, `cccd-cmnd`, `ten-nhay-cam` | **Không.** Sổ chỉ ghi nhận "bị phán oan"; muốn đổi phải sửa mã và anh duyệt. |
| **Mềm** | `so-dien-thoai-vn`, `so-tai-khoan`, `loai-tep-khong-quet-duoc`, `qua-lon-de-quet`, `ooxml-qua-lon`, `khong-doc-duoc-ooxml`, `khong-doc-duoc` | Có, cho đúng tệp đó, đúng nội dung đó. |

Sổ bài học chấm từng luật: lần chặn · tệp · đã phán xử · oan · tỉ lệ oan. **Dưới 5 phán xử ghi "chưa đủ dữ liệu"**, không kết luận. Đủ mẫu và luật mềm báo oan từ 50% trở lên thì máy **đề xuất** anh xem lại cấu hình (ví dụ `cho_phep_duoi_khong_quet`), máy không tự nới. Chốt chặn không áp "80% thắng / 20% thử": không thử nới luật để xem có lọt không.

Bộ kiểm nhanh không cần tệp thật: `python hoc_tu_chan.py --kiem` (phải in `KIỂM: ĐẠT`).

## Giới hạn

- Luật quét là **chặn thà nhầm còn hơn lọt**: có thể chặn nhầm tệp lành. Xem `chan-*.txt` và chỉnh nguồn nếu cần, không nới luật bừa.
- Luật số điện thoại có thể chặn nhầm dãy số trông giống SĐT.
- `--max-age 2d` nghĩa là tệp không sửa quá 2 ngày không được đẩy lại. Lần đầu muốn đẩy toàn bộ thì đặt `max_age` lớn (ví dụ `3650d`), chạy xong đặt về `2d`.
- Chưa thử với rclone và Google Drive thật; 71 ca kiểm thử dùng bản giả lập rclone (`python -m pytest -q`), trong đó 17 ca cho Harness² vòng 2.
