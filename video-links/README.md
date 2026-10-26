# Link video YouTube · TikTok + Mở tệp trong thư mục + thanh %

Gồm 2 phần, chỉ dùng thư viện chuẩn của Python:

- `video_links.py`: logic thuần (nhận dạng nền tảng, tổng kết, mở tệp trong thư mục). Chạy `python video_links.py so_video.json` để in bảng tổng kết Markdown.
- `video_links_ui.py`: giao diện Tkinter. Chạy `python video_links_ui.py so_video.json`.

## Giao diện
- Bảng: Mã · Tên · Nền tảng · Trạng thái · % · Link · Tệp.
- **Bấm chọn một dòng**, rồi: nút thanh công cụ **📂 Mở thư mục chứa tệp**, menu **Tệp → 📂 Mở tệp trong thư mục** (Ctrl+O), chuột phải, nhấp đúp hoặc phím Enter. Windows mở Explorer và chọn sẵn tệp; tệp mất thì mở thư mục chứa nó.
- Thanh **% tiến độ** ở dưới: tỉ lệ video đã đăng trên tổng số đang hiện (đổi theo bộ lọc Tất cả / YouTube / TikTok). Cột % là tiến độ từng video.
- 🌐 Mở link, 📋 Chép link.

## Dữ liệu vào (`so_video.example.json`)
Mỗi video: `ma`, `ten`, `url`, `tep` (đường dẫn .mp4 trên PC), `trang_thai` (`cho-dang | dang-dang | da-dang | loi`), `tien_do` (0-100), `nen_tang` (tùy chọn, tự nhận từ link). Hỗ trợ JSON hoặc CSV. Chỉ link `http/https` được nhận; đường dẫn tệp có dấu `"` hoặc xuống dòng bị từ chối. Ứng dụng không bao giờ chạy tệp, chỉ hiện tệp trong thư mục.

## Nhúng vào app .exe có sẵn
```python
import video_links as vl, video_links_ui as ui
panel = ui.VideoLinksPanel(khung_cha, vl.load_videos("so_video.json"))   # hoặc dựng list[Video] từ dữ liệu app
panel.pack(fill="both", expand=True)
ui.tao_menu(root, panel)          # thanh menu có "Mở tệp trong thư mục"
panel.cap_nhat(videos_moi)        # gọi lại khi tiến độ đổi
```
Người giữ app (CC-QLVIP) chỉ cần chuyển bản ghi video trong sổ hiện có sang các trường ở trên.

## Kiểm thử
`python -m pytest -q`: 40 ca logic. Các ca giao diện tự bỏ qua khi máy không có Tkinter hoặc màn hình; CI Windows chạy chúng thật.
