import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ton_dong as td  # noqa: E402

HEADER_TH = ["ParentSKU", "Tên", "Tồn bán sàn (30 LL+vV, có IMEI)", "Tồn HTsoft mọi kho", "Tồn Nhanh", "Giá lẻ HTsoft",
             "Giá cũ HTsoft", "NCC rẻ nhất (NỘI BỘ)"]
TODAY = date(2026, 10, 26)


def write_csv(path, rows):
    import csv
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


@pytest.fixture
def files(tmp_path):
    th = tmp_path / "th.csv"
    write_csv(th, [HEADER_TH,
                   ["MASSTEL IZI 16 4G", "Masstel", "15", "79", "15", "390.000", "", "599.000"],
                   ["XIAOMI REDMI 9A", "Redmi 9A", "10", "47", "10", "2.490.000", "", "599.000"],
                   ["NOKIA 105 4G PRO", "Nokia", "716", "724", "716", "780.000", "", "599.000"],
                   ["SIM VIETTEL 200K", "Sim", "0", "61", "0", "200.000", "200.000", ""],
                   ["BAN CHAY", "Bán chạy", "5", "5", "5", "1.000.000", "", ""],
                   ["MOI", "Mới", "3", "3", "3", "1.000.000", "", ""]])
    ls = tmp_path / "ls.csv"
    rows = [["Ngày", "ParentSKU", "Tồn bán sàn", "Giá HTsoft"]]
    for day in (1, 5, 10, 20):
        d = f"2026-10-{day:02d}"
        rows += [[d, "MASSTEL IZI 16 4G", "15", "389000"], [d, "XIAOMI REDMI 9A", "10", "2490000"],
                 [d, "NOKIA 105 4G PRO", "716", "780000"], [d, "BAN CHAY", str(10 - day // 5), "1000000"]]
    rows += [["2026-10-20", "MOI", "3", "1000000"]]
    write_csv(ls, rows)
    return th, ls


# ---------------------------------------------------------------- số kiểu Việt


@pytest.mark.parametrize("text,want", [("780.000", 780000), ("1.234.567", 1234567), ("716", 716), (" 42 ", 42), ("", None),
                                       ("abc", None), ("1,5", None), ("-3", -3), (None, None)])
def test_parse_number(text, want):
    assert td.parse_number(text) == want


# ---------------------------------------------------------------- tính toán


def test_du_lieu_cu_duoc_bao_dau_tien(files):
    kq = td.tinh(td.load_tong_hop(files[0]), td.load_lich_su(files[1]), hom_nay=TODAY)
    assert kq["du_lieu_cu"] and kq["ban_chup_cuoi"] == "2026-10-20" and kq["so_ngay_cu"] == 6
    assert kq["canh_bao"][0].startswith("du-lieu-cu") and "KHÔNG đáng tin" in kq["canh_bao"][0]


def test_du_lieu_moi_thi_khong_canh_bao_cu(files):
    kq = td.tinh(td.load_tong_hop(files[0]), td.load_lich_su(files[1]), hom_nay=date(2026, 10, 21), ngay_dong=10)
    assert not kq["du_lieu_cu"] and not any(c.startswith("du-lieu-cu") for c in kq["canh_bao"])


def test_chenh_ngoai_san_sap_theo_gia_tri_va_bo_sim_khoi_gia_tri(files):
    kq = td.tinh(td.load_tong_hop(files[0]), td.load_lich_su(files[1]), hom_nay=TODAY)
    c = kq["chenh_ngoai_san"]
    top = [r["sku"] for r in c["danh_sach"]]
    assert top[0] == "XIAOMI REDMI 9A" and c["danh_sach"][0]["chenh"] == 37 and c["danh_sach"][0]["gia_tri_uoc_tinh"] == 37 * 2490000
    sim = next(r for r in c["danh_sach"] if r["la_sim"])
    assert sim["chenh"] == 61 and sim["gia_tri_uoc_tinh"] is None
    assert c["gia_tri_uoc_tinh"] == 37 * 2490000 + 64 * 390000 + 8 * 780000


def test_hang_dong_la_ma_co_ton_va_so_khong_doi_du_ngay(files):
    kq = td.tinh(td.load_tong_hop(files[0]), td.load_lich_su(files[1]), hom_nay=TODAY, ngay_dong=14)
    skus = {r["sku"]: r for r in kq["hang_dong"]["danh_sach"]}
    assert set(skus) == {"MASSTEL IZI 16 4G", "XIAOMI REDMI 9A", "NOKIA 105 4G PRO"}
    assert skus["XIAOMI REDMI 9A"]["so_ngay_khong_doi"] == 19  # 01/10 → 20/10
    assert "BAN CHAY" not in skus      # tồn có đổi → không đồng
    assert "MOI" not in skus           # chỉ 1 bản chụp → chưa kết luận
    assert not any(k.startswith("SIM") for k in skus)


def test_doi_so_ton_thi_chay_lai_tu_dau():
    ls = [(date(2026, 10, 1), "A", 5), (date(2026, 10, 10), "A", 4), (date(2026, 10, 25), "A", 4)]
    th = {"A": {"ten": "A", "ban_san": 4, "htsoft": 4, "gia_le": 1000000}}
    kq = td.tinh(th, ls, hom_nay=date(2026, 10, 25), ngay_dong=14)
    assert kq["hang_dong"]["danh_sach"][0]["so_ngay_khong_doi"] == 15
    kq2 = td.tinh(th, ls, hom_nay=date(2026, 10, 25), ngay_dong=16)
    assert kq2["hang_dong"]["so_ma"] == 0


def test_so_tong_hop_khop_lich_su_moi_tinh_la_dong():
    ls = [(date(2026, 10, 1), "A", 5), (date(2026, 10, 25), "A", 5)]
    th = {"A": {"ten": "A", "ban_san": 3, "htsoft": 3, "gia_le": 1}}  # sheet hiện tại đã khác lịch sử
    assert td.tinh(th, ls, hom_nay=date(2026, 10, 25))["hang_dong"]["so_ma"] == 0


def test_lich_su_rong_khong_sap():
    kq = td.tinh({"A": {"ten": "A", "ban_san": 1, "htsoft": 1, "gia_le": 1}}, [], hom_nay=TODAY)
    assert kq["du_lieu_cu"] and kq["ban_chup_cuoi"] is None and kq["hang_dong"]["so_ma"] == 0


def test_thieu_cot_bat_buoc_bao_loi_ro(tmp_path):
    p = tmp_path / "x.csv"
    write_csv(p, [["ParentSKU", "Tên"], ["A", "a"]])
    with pytest.raises(ValueError, match="Tồn bán sàn"):
        td.load_tong_hop(p)


# ---------------------------------------------------------------- không lộ cột nội bộ


def test_dau_ra_khong_chua_cot_noi_bo(files, tmp_path):
    out = tmp_path / "ra"
    rc = td.main(["--tong-hop", str(files[0]), "--lich-su", str(files[1]), "--ra", str(out), "--hom-nay", "2026-10-26"])
    assert rc == 2  # dữ liệu cũ
    blob = (out / "ton-dong.json").read_text(encoding="utf-8") + (out / "ton-dong.md").read_text(encoding="utf-8")
    assert "599" not in blob and "NCC" not in blob and "NỘI BỘ" not in blob


def test_ma_thoat_0_khi_du_lieu_moi(files, tmp_path):
    rc = td.main(["--tong-hop", str(files[0]), "--lich-su", str(files[1]), "--ra", str(tmp_path / "r"),
                  "--hom-nay", "2026-10-21", "--ngay-dong", "10"])
    assert rc == 0


def test_loi_dau_vao_tra_ma_1(tmp_path):
    assert td.main(["--tong-hop", str(tmp_path / "khong.csv"), "--lich-su", str(tmp_path / "k2.csv"), "--ra", str(tmp_path)]) == 1


def test_cli_khong_sap_khi_console_cp1252(files, tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(Path(td.__file__)), "--tong-hop", str(files[0]), "--lich-su", str(files[1]),
                           "--ra", str(tmp_path / "r"), "--hom-nay", "2026-10-26"], capture_output=True, env=env, timeout=60)
    assert b"Traceback" not in proc.stderr, proc.stderr.decode("utf-8", "replace")
    assert "Kiểm tra tồn đọng".encode("utf-8") in proc.stdout
    json.loads((tmp_path / "r" / "ton-dong.json").read_text(encoding="utf-8"))
