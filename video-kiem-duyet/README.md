# Kiểm duyệt video trước xuất bản (OCR khung hình)

Bản nâng cấp của mã `doc_anh_du_phong` anh Vĩnh gửi 27/10, đặt thành **tệp riêng `kiem_duyet_video_ocr.py`**. Lý do: trên PC, `_Shared/doc_anh_du_phong.py` là một module khác ("Đọc ảnh dự phòng": `doc_anh`, `doc_anh_nhieu`...) đang được Trợ Lý VIP, kien_thuc_tinh_hoa, gemini_nhanh, phan-tich-tep-bg gọi; thay đè sẽ làm hỏng các app đó. Hai hàm `kiem_tra_khung_hinh_hop_le` và `kiem_duyet_video_truoc_render` giữ nguyên tên và chữ ký.

## Đã thử thật trên PC (28/10/2026, CC-QLVIP)
- Tesseract 4.13 (eng/osd/vie), opencv 4.13, pytesseract: `--kiem` 11/11.
- Video sạch đã đăng (Samsung A06, 20,27 s): **ĐẠT**, quét 6 khung (1/3/5 s + 3 giây cuối), chạy 6,4 s; OCR đọc đúng giá, tên máy, quà tặng; không bắt nhầm SĐT từ "10/2026", "5000", "2.480.000".
- Video cố ý vi phạm (ffmpeg 10 s): SĐT → **CHẶN giây 3**; "Giá rẻ nhất Bến Tre" → **CHẶN giây 8** (QC-2012).
- Khung đúng lúc chuyển cảnh OCR đọc rỗng → chấp nhận, không chặn.

## Sửa so với bản gốc
1. **Bỏ số hotline gán cứng** trong mã (kho công khai không được chứa SĐT). SĐT bị bắt bằng mẫu chung; có ca kiểm thử bảo đảm mã nguồn không chứa SĐT.
2. **Đóng băng an toàn:** không mở được video, không đọc được độ dài, không lấy được khung hình, hoặc thiếu Tesseract/cv2 → **CHẶN**. Bản gốc trả "đủ điều kiện" trong các trường hợp đó.
3. **SĐT theo OCR:** dính số bị tách "09xx xxx xxx" / "09xx.xxx.xxx" trước khi so; không bắt nhầm IMEI hay mã vận đơn dài hơn 10 số.
4. **Giây quét theo độ dài thật:** 1/3/5 s + 3 giây cuối. Bản gốc quét cứng 18–20 s nên video 16 s không được quét phần cuối.
5. **Thêm luật QC-2012:** "số 1, rẻ nhất, tốt nhất, hàng đầu, duy nhất, dẫn đầu" bị chặn; so sau khi bỏ dấu nên OCR mất dấu vẫn bắt. Thêm từ cấm riêng qua `tu-cam-them.json` cạnh tệp (danh sách chuỗi).

## Dùng
```
python kiem_duyet_video_ocr.py "D:\20 Kenh MXH\A04\A04 - TikTok YouTube.mp4"   # mã thoát 0 đạt, 1 chặn
python kiem_duyet_video_ocr.py --kiem                                             # tự kiểm luật chữ, không cần OCR
python kiem_duyet_video_ocr.py "<video.mp4>" --chi-tiet                           # thử video thật: in chữ OCR từng khung
```

## Thử 1 video thật trên PC trước khi thay bản cũ
1. Chạy `--kiem` (phải 11/11) rồi chạy 1 video đã đăng với `--chi-tiet`, ghi log ra tệp.
2. Đọc dòng `OCR:` từng khung: chữ giá/tên máy đọc có đúng không, có bắt nhầm SĐT/từ cấm không.
3. Thử thêm 1 video cố ý có SĐT (hoặc ảnh có số) → phải CHẶN đúng giây.
4. Chỉ khi 2 lần trên đúng mới chép vào `_Shared/kiem_duyet_video_ocr.py` và nối vào bước trước khi đăng của `tu-dong-dang-video.py`:

```python
from kiem_duyet_video_ocr import kiem_duyet_video_truoc_render
ok, ly_do = kiem_duyet_video_truoc_render(duong_dan_mp4)
if not ok:
    ghi_log(f"KHÔNG ĐĂNG: {ly_do}"); return
```
Cần `opencv-python`, `pytesseract` và Tesseract có gói tiếng Việt trên PC. Kiểm thử (33 ca) chạy không cần hai thứ đó nhờ hàm lấy khung và OCR tiêm vào được.

Giới hạn: OCR trên hình nhỏ, chữ nghiêng có thể đọc sót; đây là lớp chặn cuối, không thay cho `kiem_duyet_bai` của bộ dựng.

## Đã nối trên PC (28/10/2026 04:37, CC-QLVIP) — bài học Harness² vòng 2
- Nối tại cổng chặn chung của `tu-dong-dang-video.py` (sau dựng mp4, trước tải lên), áp cho cả nháp cũ và bài mới. Không đạt → bỏ qua video đó, ghi tin Bridge `canh-bao`/`video-bi-chan`, cả lô vẫn chạy.
- **Chỉ quét bản không SĐT** (TikTok/YouTube và sàn). Bản "Web Zalo FB" có hotline hợp lệ trên hình nên KHÔNG quét, nếu quét thì mọi bài Facebook bị chặn nhầm.
- Nhớ kết quả theo tệp + mtime (`kiem-duyet-video-ocr.json`), dựng lại video thì quét lại; tin cảnh báo chỉ gửi 1 lần mỗi tệp. Đo thật: 8,6 s video sạch, 4,5 s video bị chặn ở giây 3; lô đầu ~100 video khoảng 10–15 phút, chỉ một lần.
- Cờ `--thu-ocr <mp4>...` của `tu-dong-dang-video.py` chạy đúng cổng chặn mà không đăng, dùng để thử lại sau này.
