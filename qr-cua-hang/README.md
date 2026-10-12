# QR tại cửa hàng (học theo "quét QR tại bàn" của iPOS O2O)

Mỗi tem QR mang sẵn vị trí, giống mã bàn ở quán: `?sku=…&cn=30LL&ke=A3&nguon=tem`. Khách quét bằng camera, không cần cài app.

| Mục tiêu | Khách làm gì | Hệ thống làm gì |
|---|---|---|
| (a) Giảm tải tư vấn | Xem giá, tồn tại chi nhánh, thông số; bấm **"Cần tư vấn tại kệ này"** | Ghi 1 tệp `qr-tu-van-*.json` vào thư mục Chuông, có tên SP + chi nhánh + kệ |
| (b) Danh sách khách qua bảo hành | QR trên phiếu bảo hành (`nguon=bh&imei=…`): để lại SĐT, **tick đồng ý** | Lưu SĐT + IMEI + phiên bản điều khoản + giờ, ở thư mục riêng; có nút rút đồng ý |
| (c) Đo hiệu quả ấn phẩm | Quét QR trên tem / poster / standee / wobbler | Mỗi lượt quét ghi `nguon`; `/bao-cao` đếm theo nguồn, chi nhánh, SP |

## Luật đã cài sẵn

- **Giá fail-closed:** tệp giá cũ hơn 15 phút hoặc đọc lỗi → trang hiện "Liên hệ nhân viên để báo giá", không hiện giá cũ.
- **Không lộ giá vốn:** tệp giá có trường giá vốn/giá nhập/NCC/lợi nhuận → bị từ chối cả tệp. Tem in **không in giá**.
- **DLCN (NĐ 13/2023):** không tick đồng ý thì không lưu. SĐT không bao giờ vào tệp sự kiện hay báo cáo. Thư mục SĐT nằm trong Drive thì app không chạy.
- **Sàn TMĐT:** không đặt QR này trong ảnh hay bài đăng Shopee, Lazada, TikTok. QR chỉ dùng tại cửa hàng và trên ấn phẩm in.

## Cài trên PC (giao phiên Claude Code PC)

1. `pip install -r requirements.txt`
2. Sao chép `config.env.example` thành `config.env`, điền đường dẫn và token.
3. Tạo tệp giá công khai `qr-gia-live.json` từ `products.live.json`/SQL, mỗi 5 phút một lần (chỉ sku, ten, gia, ton theo chi nhánh, thong_so).
4. Chạy: `uvicorn app:create_app_from_env --factory --host 127.0.0.1 --port 8770`, đăng ký dịch vụ bằng NSSM.
5. Mở ra Internet cho điện thoại khách: Tailscale Funnel hoặc tên miền con của dienmayvip.com trỏ vào cổng 8770.
6. Chuông: đọc thư mục `QR_THU_MUC_CHUONG`, mỗi tệp mới là một chuông "Khách cần tư vấn tại kệ …".
7. In tem: lập `danh-sach.csv` (cột `sku,ten,cn,ke,nguon`) rồi chạy `python tao_tem.py danh-sach.csv https://<địa-chỉ> tem.pdf` (18 tem/A4).

## Kiểm thử

`pip install pytest httpx` rồi `python -m pytest -q tests` (11 ca).

Chưa thử: tệp giá thật từ SQL, Funnel thật, Chuông đọc thư mục. Cần thử trên máy trước khi dán tem.
