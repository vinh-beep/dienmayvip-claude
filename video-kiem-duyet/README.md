# Kiểm duyệt video trước xuất bản (OCR khung hình)

Bản nâng cấp của `_Shared/doc_anh_du_phong.py` anh Vĩnh gửi 27/10. Giữ nguyên 2 hàm `kiem_tra_khung_hinh_hop_le` và `kiem_duyet_video_truoc_render` để app dựng video gọi như cũ.

## Sửa so với bản gốc
1. **Bỏ số hotline gán cứng** trong mã (kho công khai không được chứa SĐT). SĐT bị bắt bằng mẫu chung; có ca kiểm thử bảo đảm mã nguồn không chứa SĐT.
2. **Đóng băng an toàn:** không mở được video, không đọc được độ dài, không lấy được khung hình, hoặc thiếu Tesseract/cv2 → **CHẶN**. Bản gốc trả "đủ điều kiện" trong các trường hợp đó.
3. **SĐT theo OCR:** dính số bị tách "09xx xxx xxx" / "09xx.xxx.xxx" trước khi so; không bắt nhầm IMEI hay mã vận đơn dài hơn 10 số.
4. **Giây quét theo độ dài thật:** 1/3/5 s + 3 giây cuối. Bản gốc quét cứng 18–20 s nên video 16 s không được quét phần cuối.
5. **Thêm luật QC-2012:** "số 1, rẻ nhất, tốt nhất, hàng đầu, duy nhất, dẫn đầu" bị chặn; so sau khi bỏ dấu nên OCR mất dấu vẫn bắt. Thêm từ cấm riêng qua `tu-cam-them.json` cạnh tệp (danh sách chuỗi).

## Dùng
```
python doc_anh_du_phong.py "D:\20 Kenh MXH\A04\A04 - TikTok YouTube.mp4"   # mã thoát 0 đạt, 1 chặn
python doc_anh_du_phong.py --kiem                                             # tự kiểm luật chữ, không cần OCR
python doc_anh_du_phong.py "<video.mp4>" --chi-tiet                           # thử video thật: in chữ OCR từng khung
```

## Thử 1 video thật trên PC trước khi thay bản cũ
1. Chạy `--kiem` (phải 11/11) rồi chạy 1 video đã đăng với `--chi-tiet`, ghi log ra tệp.
2. Đọc dòng `OCR:` từng khung: chữ giá/tên máy đọc có đúng không, có bắt nhầm SĐT/từ cấm không.
3. Thử thêm 1 video cố ý có SĐT (hoặc ảnh có số) → phải CHẶN đúng giây.
4. Chỉ khi 2 lần trên đúng mới thay `_Shared/doc_anh_du_phong.py`.
Cần `opencv-python`, `pytesseract` và Tesseract có gói tiếng Việt trên PC. Kiểm thử (33 ca) chạy không cần hai thứ đó nhờ hàm lấy khung và OCR tiêm vào được.

Giới hạn: OCR trên hình nhỏ, chữ nghiêng có thể đọc sót; đây là lớp chặn cuối, không thay cho `kiem_duyet_bai` của bộ dựng.
