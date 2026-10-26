# Chuẩn Harness² cho mọi app — bộ kiểm chỉ đọc, 0 token

Áp Harness² vào "tất cả app.exe" bắt đầu bằng việc biết app nào đã đạt khung tự kiểm. `kiem_chuan_app.py` quét các thư mục app và chấm:

| Mục | Ý nghĩa | Bắt buộc |
|---|---|---|
| kiem | có lệnh `--kiem` (tự kiểm, Harness² dùng để chấm sau khi vá) | ✅ |
| help | có `HELP.md` (F1 dùng chung `_Shared\f1_help.py`) | ✅ |
| bi-mat | không có khoá / mật khẩu gán cứng trong mã | ✅ |
| kien-thuc | có `KIEN-THUC-APP.md` | khuyến nghị |
| log | ghi log ra tệp | khuyến nghị |
| trang-thai | ghi `trang-thai*.json` | khuyến nghị |
| bak | có bản `.bak-*` | khuyến nghị |

Ghi chú tự động theo luật 26/10: `loi.log` cũ hơn lần sửa mã cuối → lỗi đã sửa, Harness² không vá lại.

```
python kiem_chuan_app.py --goc "C:\Service" --goc "C:\ClaudeVIP" --ra "C:\AIVIP\state\chuan-app"
```
Ghi `chuan-app.md` (bảng ✅/❌) và `chuan-app.json`; mã thoát 1 nếu có app hỏng mục bắt buộc. Không sửa app nào. Dùng `--bat-buoc kiem,help,bi-mat` để đổi danh sách bắt buộc.

Kiểm thử: `python -m pytest -q` (7 ca).
