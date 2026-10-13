"""Kiểm thử bộ đọc bảng giá Telegram. Mọi con số ở đây là GIẢ, không phải giá NCC thật."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doc_bang_gia_telegram import doc_gia, doc_van_ban, ra_csv, tach_dong  # noqa: E402

MAU_TIN = """[01/01/2026 09:00:00] NCC: Tồn SS *Chưa kích Ngày 01/01/2026*
+ A001 (4/128): *1.234k. Đen. Xanh*Update mới*
+ B02S(4/64): *2.345k Đen Xanh Tím.
+ B03(4/64): Xanh Dương. X La. Bac: 3.456k - *Kèm Cóc . 25W- Có cáp*. SL ít
+ S99 FE 126G: X Lá. Xám . X Dương : *11.111- Đã trừ ST*
+ S99ultra (256): 22.222k (đen,trắng, tím)
+ Zfold 9 - F999 256G: 33.333k . Đen
+ Tab Z1 128G WIFI/ X999: Xám, Bạc : 12.121k
+ Fit 9/ R999: Bạc Xám : 555k *Tạm hết*
+ *Buds X / R998: Đen 666k*Sl ít
✅ *A e check thêm giá theo BG*✅
[01/01/2026 09:01:00] NCC: 01/01 SAMSUNG - Hàng Kích Hoạt
+ A01 (4/64): Xanh Đen Tim: 1.111k- SL 10: 1.100k
+ B02S( 4/64): Đen Xanh Tím: 2.222k- SL 2.200k
+ Tab Z2 4G ( X998 ) 4G/64G Bạc Xám : *3.333k .SL 5c : 3.300k*
+ S99 FE 128: Xám. X Lá. X Blue: 9.999k
"""


def test_doc_gia():
    assert doc_gia("5.360k") == 5_360_000
    assert doc_gia("16.890") == 16_890_000
    assert doc_gia("990k") == 990_000
    assert doc_gia("1.020k") == 1_020_000


def test_so_tron_khong_phai_gia():
    dh = tach_dong("+ S99ultra (256): 22.222k (đen,trắng, tím)")
    assert dh.gia == [(1, 22_222_000)]
    assert dh.cau_hinh == "256"
    assert dh.ten == "S99ultra"
    assert dh.mau == ["Den", "Tim", "Trang"]


def test_gia_co_dau_cham_sau_k():
    dh = tach_dong("+ A001 (4/128): *5.360k. Đen. Xanh*Update mới*")
    assert dh.gia == [(1, 5_360_000)]
    assert dh.ten == "A001" and dh.model == "A001"
    assert dh.cau_hinh == "4/128"
    assert dh.mau == ["Xanh", "Den"]
    assert dh.ghi_chu == ["Update moi"]


def test_bac_so_luong():
    dh = tach_dong("+ A01 (4/64): Xanh Đen Tim: 1.111k- SL 10: 1.100k")
    assert dh.gia == [(1, 1_111_000), (10, 1_100_000)]
    dh = tach_dong("+ Tab Z2 4G ( X998 ) 4G/64G Bạc Xám : *3.333k .SL 5c : 3.300k*")
    assert dh.gia == [(1, 3_333_000), (5, 3_300_000)]
    assert dh.ten == "Tab Z2 4G" and dh.model == "X998" and dh.cau_hinh == "4/64"


def test_sl_khong_ghi_so():
    dh = tach_dong("+ B02S( 4/64): Đen Xanh Tím: 2.222k- SL 2.200k")
    assert dh.gia == [(1, 2_222_000), (0, 2_200_000)]
    assert any("hoi lai" in g for g in dh.ghi_chu)


def test_ma_model_va_ten():
    dh = tach_dong("+ Zfold 9 - F999 256G: 33.333k . Đen")
    assert (dh.ten, dh.model, dh.cau_hinh, dh.mau) == ("Zfold 9", "F999", "256", ["Den"])
    dh = tach_dong("+ Tab Z1 128G WIFI/ X999: Xám, Bạc : 12.121k")
    assert (dh.ten, dh.model, dh.cau_hinh) == ("Tab Z1 WIFI", "X999", "128")
    dh = tach_dong("+ X998 4G( 4/64): Bạc Xám : 4.444k")
    assert (dh.ten, dh.model) == ("X998 4G", "X998")
    dh = tach_dong("+ *Buds X / R998: Đen 666k*Sl ít")
    assert (dh.ten, dh.model, dh.gia) == ("Buds X", "R998", [(1, 666_000)])


def test_ghi_chu_kem_coc():
    dh = tach_dong("+ B03(4/64): Xanh Dương. X La. Bac: 3.456k - *Kèm Cóc . 25W- Có cáp*. SL ít")
    assert dh.mau == ["Xanh duong", "Xanh la", "Bac"]
    assert "Kem Coc" in dh.ghi_chu and "Co cap" in dh.ghi_chu


def test_khoi_chua_kich_va_da_kich():
    cac = doc_van_ban(MAU_TIN)
    loai = [l for l, _ in cac]
    assert loai.count("Chua kich hoat") == 9
    assert loai.count("Da kich hoat") == 4
    hang = ra_csv(cac, "NCC Thu", "01/01/2026")
    assert len(hang) == 9 + 4 + 3  # 3 dòng có bậc SL
    assert set(h["NCC"] for h in hang) == {"NCC Thu"}
    assert hang[0]["TenHang"] == "A001 (4/128)"
    assert hang[-1]["TenHang"] == "S99 FE (128)"


def test_dong_khong_phai_hang_bo_qua():
    assert tach_dong("✅ *A e check thêm giá theo BG*✅") is None
    assert tach_dong("+ Hàng không ghi giá") is None
