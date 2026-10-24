# Bảng giá NCC từ Telegram → CSV `dmv_GiaNCC`

Script `doc_bang_gia_telegram.py` đọc tin bảng giá nhà cung cấp dán nguyên từ Telegram
(kiểu "MD Samsung": khối *Chưa kích* và khối *Hàng Kích Hoạt*, mỗi mặt hàng một dòng `+`)
và xuất CSV cùng cột với bảng `dmv_GiaNCC`:

```
NgayBaoGia,NCC,NhomHang,TenHang,Model,MauSac,LoaiHang,BaoHanh,SL_Min,DonGia_VND,GhiChu
```

## Luật bắt buộc

- CSV kết quả **chứa giá nhập**. Không commit vào kho này, không upload lên Drive Bridge
  (sổ chuẩn Phần A mục 3, Phụ lục 28/07). Chỉ nhập vào SQL `dbtest.dmv_GiaNCC` trên PC
  hoặc lưu `D:\VIP DATA\02 Bang Gia NCC`.
- Kho này chỉ giữ **mã nguồn và kiểm thử với số giả**.

## Cách chạy (PC, PowerShell)

```
python doc_bang_gia_telegram.py --ncc "Ten NCC" --ngay 13/10/2026 --vao tin.txt --ra bang-gia.csv
```

`tin.txt` = dán nguyên tin Telegram (giữ cả dòng tiêu đề "Chưa kích" / "Hàng Kích Hoạt").

## Quy ước đọc tin NCC (đã kiểm với bảng thật 13/10/2026, 31 mặt hàng)

| Trong tin | Hiểu là |
|---|---|
| `5.360k`, `16.890`, `990k` | giá theo nghìn đồng → 5.360.000 / 16.890.000 / 990.000 |
| `(4/128)`, `8G/128G` | RAM/ROM → `TenHang` ghi `(4/128)` |
| `(256)`, `256G`, `128:` | chỉ ROM → `(256)` |
| `A076`, `X135`, `F966`, `R410` | mã model Samsung → cột `Model`; dòng chỉ có mã thì `TenHang` = mã |
| `3.230k- SL 10: 3.200k` | 2 dòng: SL_Min 1 và SL_Min 10 |
| `3.390k- SL 3.370k` (SL không số) | dòng 2 có SL_Min = 0 + ghi chú "hỏi lại" |
| `*...*` và phần sau giá | ghi chú: Kèm Cóc 25W, Tạm hết, Đã trừ ST, Giá ĐB, New Model… |
| Khối "Chưa kích" / "Kích Hoạt" | `LoaiHang` = `Chua kich hoat` / `Da kich hoat` |

Màu được chuẩn hoá không dấu: Den, Trang, Xanh, Xanh duong, Xanh la, Tim, Xam, Bac, Hong.
Số trơn không có `k` và không có dấu chấm nghìn (vd `128`, `256`) **không** bị hiểu là giá.

## Kiểm thử

```
python -m pytest bang-gia-ncc/tests -q
```
