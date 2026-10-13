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

## Luật
- Tệp `du-lieu\bao-gia-ncc.json` và CSV xuất ra **chứa giá nhập**: không chép lên Drive Bridge,
  không đưa vào kho công khai (sổ chuẩn Phần A mục 3). Nên đặt app tại `D:\VIP DATA\02 Bang Gia NCC\`.
- Kho này chỉ giữ mã nguồn và kiểm thử với số giả.

## Build lại
Cần Go ≥ 1.24. Trên Linux/macOS: `./build.sh`. Trên Windows: `build.bat`.
Kết quả: `QuanLyBaoGiaNCC-KhuongViet.exe` (khoảng 6,5 MB). Kiểm thử: `go test ./...`.

Chạy với thư mục dữ liệu khác: `QuanLyBaoGiaNCC-KhuongViet.exe "D:\VIP DATA\02 Bang Gia NCC\du-lieu"`.
