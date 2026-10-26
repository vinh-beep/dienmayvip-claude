# Tổng kết tự động Bridge (kiểu Lark Mail VIP)

Anh Vĩnh yêu cầu 26/10/2026: mọi app (.exe, Python, cmd) đều ghi việc gấp lên Bridge nhưng chưa ai **gom và tổng kết theo danh mục**. Bộ này làm đúng việc đó, **0 token** (không gọi AI), chạy trên PC.

## Làm gì
1. Đọc mọi `tin-*.json`, `ket-qua-*.json`, `ket-qua-*.md`, `luat-*.json` trong thư mục Bridge, cửa sổ 24 giờ (đổi bằng `--gio`).
2. Chia 5 danh mục: **① GẤP** (tin có `can_xac_nhan`, loại `viec`, hoặc có chữ "cần anh/chờ anh/duyệt") · **② LỖI** (cảnh báo, mã lỗi, FAILED, invalid_grant…) · **③ XONG** · **④ LUẬT** · **⑤ Khác**.
3. **Loại trùng**: cùng chủ đề + cùng 60 ký tự đầu → giữ bản mới nhất (tin gửi lại nhiều lần chỉ còn 1 dòng).
4. **Tự gắn cách chữa** cho lỗi đã biết từ `loi_biet.json` (mã 1073807364, 267014, 0xc0000142, invalid_grant, disabled subscription, 08001…). Thêm lỗi mới vào tệp này, không xoá mục cũ.
5. **Che** SĐT, email, CCCD, số tài khoản trước khi ghi.
6. Ghi 3 tệp vào Bridge: `TONG-KET-TU-DONG-<dd MM yyyy HHhmmp>.md`, `TONG-KET-TU-DONG-moi-nhat.md` (đè), `TONG-KET-TU-DONG-moi-nhat.json` (cho app .exe/Chuông VIP đọc).
7. Đầu tệp là **KHỐI SAO CHÉP TOÀN BỘ**: mỗi việc 1 dòng có số thứ tự, bôi đen dán thẳng vào Zalo/Lark được.

## Chạy trên PC
```
python tong_ket.py --bridge "C:\DMV-Cloud-Bridge"            # ghi ngay vào Bridge
python tong_ket.py --bridge "C:\DMV-Cloud-Bridge" --gio 48    # 48 giờ
```
Gắn vào lịch có sẵn của Harness² (ví dụ ngay sau bản tin trạng thái mỗi 30 phút, hoặc 2 lần/ngày 07h40 và 15h40 trước lượt tổng hợp Cloud). Chạy lại cùng dữ liệu ra cùng kết quả, không nhân đôi.

## Kiểm thử
`python test_tong_ket.py` — 8 ca: phân loại, loại trùng giữ bản mới, che PII, gắn cách chữa, bỏ tệp cũ/rác, có khối sao chép, chạy lại không đổi, không tự đọc lại chính nó.

## Giới hạn
- Chỉ đọc tệp có tiền tố chuẩn (`tin-`, `ket-qua-`, `luat-`). App nào ghi tên khác thì đổi tên theo chuẩn hoặc thêm vào `doc_tep`.
- Phân loại theo từ khoá, không hiểu nghĩa; việc nào xếp sai thì sửa từ khoá trong `RE_GAP/RE_LOI/RE_XONG`.
