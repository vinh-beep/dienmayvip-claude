# drive-sync — Trợ giúp nhanh (F1)

Đẩy thư mục đã chọn lên Google Drive bằng rclone. Có quét an toàn trước khi đẩy và Harness² vòng 2 cho bộ chặn. Chi tiết đầy đủ: `README.md`.

## Lệnh hay dùng

| Việc | Lệnh |
|---|---|
| Chạy thử (không ghi gì lên Drive) | `python dong_bo_drive.py --config dong_bo.config.json` |
| Chạy thật | thêm `--chay-that` |
| Kiểm nhẹ (cấu hình + thư mục, không mạng) | `python dong_bo_drive.py --config dong_bo.config.json --kiem-nhe` |
| Kiểm đầy đủ (thêm rclone + remote) | `python dong_bo_drive.py --config dong_bo.config.json --kiem` |
| Báo nếu quá 24 giờ chưa đẩy được | `python dong_bo_drive.py --config dong_bo.config.json --kiem-tuoi` |
| Xem sổ bài học bộ chặn | `python hoc_tu_chan.py --config dong_bo.config.json` rồi mở `log\so-bai-hoc-chan.md` |
| Phán xử tệp bị chặn | `python hoc_tu_chan.py --config dong_bo.config.json --phan-xu "BaoCao/tep.pdf=oan"` (hoặc `=dung`) |
| Tự kiểm bộ học | `python hoc_tu_chan.py --kiem` (phải in `KIỂM: ĐẠT`) |

## Mã thoát

- `dong_bo_drive.py`: 0 ổn · 1 có lỗi · 2 quá hạn chưa đồng bộ.
- `hoc_tu_chan.py`: 0 ổn · 1 lỗi cấu hình hoặc đầu vào.

## Tệp trong thư mục log

| Tệp | Ý nghĩa |
|---|---|
| `trang-thai-dong-bo.json` | kết quả lượt cuối, có cột `theo_bai_hoc` |
| `chan-<giờ>.txt` | tệp bị chặn và luật chặn (không ghi nội dung) |
| `phan-xu-chan.json` | phán xử oan/đúng của anh |
| `bai-hoc-chan.json` · `so-bai-hoc-chan.md` | sổ bài học máy sinh lại mỗi lượt |

## Nhớ

- Luật cứng (bí mật, giá vốn, CCCD, tên tệp nhạy cảm) không bao giờ được nới, dù phán "oan".
- Tệp phán "oan" chỉ qua khi nội dung chưa đổi. Sửa tệp thì phải phán lại.
- Chỉ `copy`, không bao giờ xoá trên Drive.
