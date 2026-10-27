# Harness² — luật cho mọi vòng tự động của DienmayVIP

Kho này **công khai**: không giá vốn, giá NCC, SĐT, token, chuỗi kết nối. Tài liệu này là **kiến thức dùng chung** cho mọi phiên Claude (Cloud và PC); luật PHẦN A trong `DMV-INSTRUCTIONS-MASTER-v3.md` trên Bridge luôn thắng khi mâu thuẫn.

## 1. Harness² là gì

"Harness²" không phải sản phẩm bên ngoài. Đây là **bộ khung tự động nội bộ** (phiên PC-Service Các App dựng, 25/10/2026), và quan trọng hơn là **một luật thiết kế** anh Vĩnh đã chốt cho mọi việc tự chạy:

> Việc tự chạy nào có **điểm dự đoán trước khi làm** (Gemini chấm, kiểm duyệt, chốt chặn, gợi ý giá) thì phải có **vòng 2 đo kết quả thật** sau khi làm, ghi vào **sổ bài học** kèm **số mẫu**; dưới 5 mẫu ghi "chưa đủ dữ liệu". Vòng 1 lần sau **phải đọc sổ đó**: 80% theo công thức đang thắng, 20% thử mới. **Rào chắn cứng** (kiểm duyệt QC-2012, ngưỡng 75, dừng khẩn `.DUNG`, giá vốn, bí mật) **không được để vòng 2 tự nới**.

Hai vòng, nói ngắn:

| | Vòng 1 — dự đoán | Vòng 2 — đo thật |
|---|---|---|
| Video TikTok | chọn móc 3 s, giờ đăng, Gemini chấm ≥ 75 | lượt xem 1h/6h/24h/72h → `dmv_Video_GiaThuyet`, `bai-hoc.json` |
| Giá sàn Shopee | gợi ý giữ/hạ/tăng | đơn 7 ngày trước/sau, % lãi sau phí → `so-bai-hoc-gia-san.md` |
| Bộ chặn drive-sync | "tệp này nguy hiểm → chặn" | anh phán xử oan/đúng → `so-bai-hoc-chan.md` (trong kho này) |
| Đọc IMEI | mã vạch trên máy trước, AI sau | % Luhn, % khớp kho, % trùng giữa 2 nguồn → chọn nguồn rẻ |

## 2. Mười luật vận hành (H1–H10)

| Mã | Luật | Vì sao |
|---|---|---|
| H1 | Mỗi tác vụ ghi **trạng thái** bắt đầu / xong / lỗi + mã thoát ra tệp nhỏ trên Bridge (`ket-qua-PC-H2-<việc>-<giờ>`). Không ghi nội dung đầu ra. | "Xong" phải có bằng chứng; không lộ giá hay PII. |
| H2 | **Chạy bù khi khởi động lại**: lịch đã qua trong cửa sổ 12 giờ mà chưa có "xong" → chạy bù. Việc **tiền/ngân hàng** chỉ báo, không tự chạy (nhận diện theo cả nhóm `tien` lẫn tên BANK/NGÂN HÀNG/SỔ PHỤ/THANH TOÁN/CHUYỂN KHOẢN/TÀI CHÍNH). | 3 lần rớt máy trong 5 ngày (22–25/10), LENH BANK 07h00 bị lỡ không ai chạy lại. |
| H3 | **Cửa RAM**: trước tác vụ AI đọc RAM trống; thiếu thì xếp hàng, không ép nạp mô hình; tối đa 1 mô hình cục bộ cùng lúc. | RAM 62–89%, Gemma/Qwen bị dỡ liên tục, 9 nút MCP hỏng. |
| H4 | **Giám sát chính bộ giám sát**: Harness² ghi nhịp tim riêng; bản tin trạng thái hoặc `tran-ram` quá 2 nhịp → báo động. | `tran-ram-trang-thai.json` ngừng ghi từ 23/10 mà không ai biết. |
| H5 | **Kiểm quyền gom 1 lần** (Gmail/Drive/SQL) trước khi chạy; hỏng quyền → 1 báo cáo gom các việc liên quan, không chạy. | Gmail OAuth bị thu hồi 22/10 → 4 tác vụ lỗi dây chuyền. |
| H6 | **Ghi DB** theo skill `htsoft-safe-sql`: sao lưu → TRY/CATCH + TRAN → idempotent → kiểm lại. Ghi `MATHANG` phải chờ anh duyệt. | Mẫu Mua Hàng xoá dòng rác `BG_NCC` đúng quy trình. |
| H7 | **Không tự cài chạy nền** (scheduled task, tự khởi động lại app) nếu anh chưa duyệt. | Luật phiên trước. |
| H8 | **Nghiệm thu**: chỉ "sẵn sàng" khi có ≥ 1 tác vụ gọi AI thật, chạy 3 ngày liền không lỗi, vượt 1 lần khởi động lại máy. | "Chạy được" khác "làm được việc". |
| H9 | Đầu ra công khai qua máy chấm duyệt; không giá vốn, không từ cấm QC-2012. | Luật A. |
| H10 | **Chạy tuần tự**, một tiến trình mỗi lúc, `CREATE_NO_WINDOW`; không chạy song song nhiều python/node/powershell. | Máy chính treo vì cạn heap desktop (0xc0000142) khi quá nhiều console. |

Mẫu chuẩn cho mọi công cụ mới trên máy chính: **mặc định chạy thử, chỉ chạy thật khi có `--chay-that`**; có `--kiem` nhẹ (< 40 s, không SQL) tách khỏi `--kiem-day-du`.

## 3. Áp dụng trong kho này

| Module | Vòng 1 | Vòng 2 | Rào chắn cứng |
|---|---|---|---|
| `harness2-chay-bu/` (nhánh `claude/magical-volta-z46fnn`, PR #1) | lịch gốc ghi "xong" vào `trang-thai-h2.json` | lúc khởi động quét việc lỡ, chạy bù trong cửa sổ 12 giờ, ghi `ket-qua-PC-H2-*` | việc tiền không bao giờ tự chạy; cửa RAM; kiểm quyền 1 lần |
| `drive-sync/kiem_an_toan.py` + `hoc_tu_chan.py` | quét tên + nội dung, chặn fail-closed | anh phán xử oan/đúng → `bai-hoc-chan.json` + `so-bai-hoc-chan.md`; vòng 1 cho qua tệp "oan" khi SHA-256 còn khớp | `LUAT_CUNG`: bí mật, giá vốn, CCCD, tên tệp nhạy cảm — không nhận ngoại lệ |
| `drive-sync/dong_bo_drive.py` (base, 25/10) | `rclone copy` | **đọc lại đích** bằng `rclone check --one-way` sau mỗi lượt thật; hỏng thì không ghi mốc thành công ("tải về ≠ đã nạp") | chỉ `copy`, không `sync`/xoá |
| `kiem_tat_ca.py` + CI Ubuntu/Windows (base, 25/10) | bộ kiểm thử | **tự kiểm bộ kiểm** bằng đột biến: cố ý phá 27 chỗ (tắt token, tắt chặn giá vốn, `copy`→`sync`…), bộ kiểm phải đỏ | đột biến nào vẫn xanh = lỗ hổng → mã thoát 1 |
| `sql-readonly-api/` | chặn cột nghi giá vốn/PII khi khởi động; khoá IP sau 10 lần sai | *chưa có* — đề xuất: đếm số lần khoá IP oan và số view bị từ chối nhầm vào `api-audit.log`, tổng hợp hằng tuần | từ chối khởi động nếu login có quyền ghi |

### Cách nối vòng 2 vào một công cụ mới (checklist)

1. Xác định **điểm dự đoán** của vòng 1 và **kết quả thật** đo được sau khi làm (xem, đơn, báo oan, khớp kho…).
2. Vòng 1 ghi **giả thuyết** ngay khi quyết định (móc, giờ, luật, ngưỡng) — không ghi sau.
3. Vòng 2 chạy theo lịch hoặc theo lệnh, đo đúng **cửa sổ** (1h/6h/24h/72h hoặc 7 ngày), ghi **số mẫu**; `< 5 mẫu = "chưa đủ dữ liệu"`.
4. **Sổ bài học sinh lại cả tệp** mỗi lượt (mới nhất trên cùng, đánh số ①) → không nhân đôi. JSON cho máy, Markdown cho người.
5. Vòng 1 lần sau **đọc sổ**: 80% công thức đang thắng, 20% thử mới. **Chốt chặn thì không 80/20** — không thử nới luật để xem có lọt không.
6. Liệt kê rõ **rào chắn cứng** trong mã (một `frozenset`), có test chứng minh vòng 2 không nới được.
7. Ghi kết quả thật sau khi dựng: số ca kiểm thử qua, lần chạy thật, idempotent lần 2. "Chạy được" chưa phải "làm được việc" (H8).

## 4. Bẫy đã gặp (tinh hoa 25/10/2026)

- **Port POSIX → Windows**: `fcntl.flock` không có; shim bằng `msvcrt.locking(LK_LOCK)` sai (chỉ thử 10 lần/1 s rồi ném) → vòng `LK_NBLCK` + sleep 10 ms. `str(path.relative_to(root))` ra `\` → khoá dict không khớp regex kiểu `scripts/…` → dùng `.as_posix()`. Dấu hiệu: lỗi đổi chỗ mỗi lần chạy = khoá/thời gian, không phải logic.
- **Hai phiên cùng sửa một tệp** (`kien_thuc_san_pham.py`) làm hỏng 1 dòng → một người giữ tệp; phiên khác chỉ vá nhỏ + báo bảng chung.
- **Điểm AI thấp vì tư liệu, không vì lời**: A03 chỉ có 1 ảnh nên Gemini chê; sửa khuôn không cứu được thiếu ảnh.
- **Đọc thông số HTsoft ưu tiên cột số** (`PIN_MAH`, `SAC_W`, `MAN_HZ`, `MAN_INCH`) trước chuỗi; thiếu thì đưa vào hàng crawl, không bịa.
- **Bộ nạp bảng giá cắt đôi số**: regex bắt đuôi `| 37` + `40000` thành 40.000.000 → thêm `(?<![\d.,])` và loại năm 2015–2035.
- **`es` (Everything) treo**: không nối nhiều lệnh `es` trong 1 Bash; khởi động lại Everything không cứu ngay.
- **Heredoc trong Bash tool** có thể nuốt ký tự → sau khi ghi tệp bằng heredoc phải chạy lại test/compile để xác nhận.

## 5. Nhật ký (chỉ thêm)

- **25/10/2026 21h38** (Cloud): định nghĩa Harness², luật H1–H9 từ 8 tinh hoa 24–25/10.
- **25/10/2026 21h45** (anh Vĩnh duyệt): Harness² tự chạy bù việc lỡ, trừ ngân hàng/tiền, cửa sổ 12 giờ.
- **25/10/2026 21h55** (Cloud): dựng `harness2-chay-bu/`, 16/16 test, thêm H10.
- **25/10/2026 ~22h** (Cloud, nhánh base): đọc lại đích sau khi đẩy, `--kiem-nhe`/`--kiem`, `kiem_tat_ca.py --tu-kiem` (đột biến), CI Ubuntu + Windows, vá console cp1252.
- **25/10/2026 23h00** (Cloud, phiên này): thêm vòng 2 cho bộ chặn drive-sync (`hoc_tu_chan.py`, 17 test mới, 71/71 qua), chốt `LUAT_CUNG`/`LUAT_MEM`, tài liệu này.
