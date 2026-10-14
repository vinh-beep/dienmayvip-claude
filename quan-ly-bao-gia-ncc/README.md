# Quản lý báo giá NCC Khương Việt (app Windows, 1 tệp .exe)

App chạy tại máy, không cần cài gì, không gửi dữ liệu ra ngoài. Mở tệp `.exe` → trình duyệt
tự mở giao diện tại `http://127.0.0.1:8765/`. Dữ liệu (có giá nhập) nằm trong thư mục
`du-lieu\` cạnh tệp `.exe`; mỗi lần ghi đều sao lưu bản cũ vào `du-lieu\sao-luu\`.

## Hai nhóm hàng

| Nhóm trong app | Trong tin NCC | Ý nghĩa |
|---|---|---|
| **Đã tham gia CTKM Samsung** | khối "Hàng Kích Hoạt" | máy đã kích hoạt, giá thấp hơn, có bậc số lượng |
| **Chưa tham gia CTKM Samsung** | khối "Tồn SS – Chưa kích" | máy chưa kích hoạt, giá cao hơn, tồn theo màu |

## Dùng hằng ngày
1. Tab **Nhập bảng giá mới**: dán nguyên tin Telegram (giữ dòng tiêu đề Chưa kích / Kích Hoạt),
   chọn ngày → **Đọc tin Telegram** → kiểm/sửa bảng xem trước → **Lưu vào kho**.
   Hoặc nhập CSV 11 cột `dmv_GiaNCC`.
2. Tab nhóm: chọn ngày (mới nhất trên cùng), tìm theo tên/model/màu, cột **So lần trước** báo
   ▲ tăng / ▼ giảm so với bảng giá gần nhất của cùng mặt hàng và cùng bậc SL.
3. **Xuất CSV** (toàn bộ, theo nhóm, theo ngày) đúng cột `dmv_GiaNCC` để phiên PC nhập SQL.
4. "SL?" = NCC ghi bậc số lượng nhưng không ghi số, hỏi lại NCC.

## Tab HĐĐT NCC (hoá đơn điện tử)

Khương Việt phát hành hoá đơn qua **Fast e-Invoice**: email từ `einvoice@fastsoftware.com.vn`
không đính kèm tệp, chỉ có link tải XML (`type=2`) và PDF (`type=3`). App tìm hoá đơn theo 4 cách,
nguồn nào cũng gộp theo (Ký hiệu, Số HĐ), không trùng:

| Nút | Cách hoạt động | Cần gì |
|---|---|---|
| **1. Nạp từ Bridge (AI Cloud)** | Phiên Claude Cloud quét Gmail vinh@dienmayvip.com, ghi `hddt-links-*.json` (số HĐ, ký hiệu, link tải) lên Drive Bridge; app đọc tệp đó từ `G:\My Drive\DMV-Cloud-Bridge` | Drive for desktop đang chạy |
| **2. Tìm trong Gmail (IMAP)** | App tự đăng nhập IMAP, tìm thư Fast e-Invoice của NCC đang lọc | Gmail bật IMAP + *Mật khẩu ứng dụng* Google (nhập trong Cấu hình) |
| **3. Tìm bằng Everything** | Hỏi Everything HTTP server tìm `.xml/.zip/.pdf` tên có khuongviet/hoadon/hddt/C2*TKV…; đọc XML, gắn PDF theo số HĐ | Everything: Tools → Options → HTTP Server → bật, cổng 8080 (hoặc `es.exe` trong PATH) |
| **4. Quét thư mục** | Duyệt thư mục trong Cấu hình (mặc định `D:\VIP DATA\03 Ke Toan HDDT` và Downloads) | — |
| **Dán email** | Dán nội dung email Fast e-Invoice (Ctrl+A, Ctrl+C trong Gmail) | — |

Sau khi có link: **Tải XML + PDF** tải về `du-lieu\hddt\<NCC>\<KyHieu>-<So>.xml/.pdf`, đọc XML
chuẩn TT78 (số, ký hiệu, ngày, người bán, MST, từng dòng hàng, thuế, tổng). **Chi tiết** đối chiếu
mỗi dòng hoá đơn với dòng báo giá gần ngày nhất cùng model (A07, X133, S26 FE…), hiện chênh lệch
giá hoá đơn − báo giá. **Xuất CSV** ra từng dòng hàng kèm số HĐ.

Nếu Fast trả về trang web thay vì tệp (cần mã xác thực), app báo lỗi và giữ link **Tra cứu** để tải
thủ công rồi bỏ vào thư mục quét.

## Luật
- Tệp `du-lieu\bao-gia-ncc.json` và CSV xuất ra **chứa giá nhập**: không chép lên Drive Bridge,
  không đưa vào kho công khai (sổ chuẩn Phần A mục 3). Nên đặt app tại `D:\VIP DATA\02 Bang Gia NCC\`.
- Kho này chỉ giữ mã nguồn và kiểm thử với số giả.

## Build lại
Cần Go ≥ 1.24. Trên Linux/macOS: `./build.sh`. Trên Windows: `build.bat`.
Kết quả: `QuanLyBaoGiaNCC-KhuongViet.exe` (khoảng 6,5 MB). Kiểm thử: `go test ./...`.

`MO-APP.bat` cạnh .exe dùng để phiên Claude PC (hoặc Task Scheduler) mở app: dán đường dẫn .bat
vào thanh địa chỉ File Explorer rồi Enter (cách ở mục G sổ chuẩn).

Chạy với thư mục dữ liệu khác: `QuanLyBaoGiaNCC-KhuongViet.exe "D:\VIP DATA\02 Bang Gia NCC\du-lieu"`.
