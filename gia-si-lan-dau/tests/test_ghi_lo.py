import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ghi_lo_gia_si as g


TIEU_DE = ["Mã hàng", "Tên hàng", "Giá sỉ", "Giá lẻ", "Lãi trên vốn"]


def test_tim_cot_theo_tu_khoa_bo_dau():
    assert g.tim_cot(TIEU_DE, ["ma"]) == 0
    assert g.tim_cot(TIEU_DE, ["gia", "si"]) == 2
    assert g.tim_cot(TIEU_DE, ["lai"]) == 4
    assert g.tim_cot(TIEU_DE, ["xxx"], "Giá lẻ") == 3


def test_phan_tram_chap_nhan_ca_hai_dang():
    assert g.phan_tram(12) == 0.12
    assert g.phan_tram(0.12) == 0.12
    assert g.phan_tram("8,5%") == 0.085
    assert g.phan_tram(None) is None


def test_loc_lo_phan_loai_dung():
    than = [
        ("A1", "x", 1000000, 1200000, 0.05),   # sạch
        ("A2", "x", 1000000, 1200000, 0.12),   # > 10% -> loại
        ("A3", "x", 1000000, 1200000, 0),      # <= 0 -> loại
        ("A4", "x", None, 1200000, 0.05),      # giá trống -> loại
        ("A1", "x", 1000000, 1200000, 0.05),   # trùng -> loại
        ("A5", "x", 2000000, 2500000, 9),      # 9% dạng phần trăm -> sạch
        ("A6", "x", 2000000, 2500000, 0.03),   # loại trừ thủ công
        ("", "x", 1, 1, 0.01),                 # bỏ qua
    ]
    sach, loai = g.loc_lo(TIEU_DE, than, {"lai_toi_da": 0.10, "loai_tru_ma": ["a6"]})
    assert [m for m, _, _ in sach] == ["A1", "A5"]
    assert sach[0][1] == 1000000
    ly_do = {m: l for m, _, _, l in loai}
    assert "nghi ghép nhầm" in ly_do["A2"]
    assert "dưới sàn vốn" in ly_do["A3"]
    assert "không hợp lệ" in ly_do["A4"]
    assert "loại trừ" in ly_do["A6"]
    assert sum(1 for m, *_ in loai if m == "A1") == 1


def test_cot_bat_buoc_chua_co():
    cot = [
        dict(ten="ID", kieu="int", null=False, mac_dinh=None),
        dict(ten="MHCODE", kieu="nvarchar", null=False, mac_dinh=None),
        dict(ten="GiaSi", kieu="decimal", null=False, mac_dinh=None),
        dict(ten="NgayTao", kieu="datetime", null=False, mac_dinh="(getdate())"),
        dict(ten="GhiChu", kieu="nvarchar", null=True, mac_dinh=None),
    ]
    assert g.cot_bat_buoc_chua_co(cot, ["MHCODE", "GiaSi"]) == ["ID"]
