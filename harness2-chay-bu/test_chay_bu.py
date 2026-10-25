import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chay_bu as cb  # noqa: E402

VN = cb.VN


def gio(h, m=0, ngay=25):
    return datetime(2026, 10, ngay, h, m, tzinfo=VN)


VIEC = [
    {"ten": "M1-ton-kho", "lich": ["06:00"], "lenh": ["x"], "can_quyen": ["sql"], "can_ram_mb": 500},
    {"ten": "LENH-BANK-ALL", "lich": ["07:00"], "lenh": ["x"]},
    {"ten": "tai-chinh-doi-soat", "lich": ["07:30"], "nhom": "thuong", "lenh": ["x"]},
    {"ten": "ban-tin-email", "lich": ["08:00"], "lenh": ["x"], "can_quyen": ["gmail"]},
    {"ten": "dem-cu", "lich": ["00:30"], "lenh": ["x"], "cua_so_gio": 6},
]


class KeHoach(unittest.TestCase):
    def test_may_rot_05h53_len_13h46(self):
        # Đúng kịch bản 25/10: máy chết 05h53-13h45.
        kh = cb.lap_ke_hoach(VIEC, {"dem-cu": {"xong": gio(0, 31).isoformat()}}, gio(13, 46))
        self.assertEqual([v["ten"] for v in kh["chay_bu"]], ["M1-ton-kho", "ban-tin-email"])
        self.assertEqual({v["ten"] for v in kh["chi_bao_tien"]}, {"LENH-BANK-ALL", "tai-chinh-doi-soat"})
        self.assertEqual(kh["da_xong"], ["dem-cu"])

    def test_qua_cua_so(self):
        kh = cb.lap_ke_hoach(VIEC, {}, gio(13, 46))
        self.assertIn("dem-cu", [v["ten"] for v in kh["qua_cua_so"]])

    def test_lich_hom_qua(self):
        # 02h sáng: lịch 08:00 gần nhất là hôm qua; 18 giờ > 12 giờ cửa sổ -> quá cửa sổ.
        kh = cb.lap_ke_hoach([VIEC[3]], {}, gio(2))
        self.assertEqual(kh["qua_cua_so"][0]["hen"], "2026-10-24T08:00+07:00")

    def test_da_xong_sau_gio_hen(self):
        kh = cb.lap_ke_hoach([VIEC[0]], {"M1-ton-kho": {"xong": gio(6, 5).isoformat()}}, gio(13))
        self.assertEqual(kh["chay_bu"], [])

    def test_xong_truoc_gio_hen_van_chay_bu(self):
        kh = cb.lap_ke_hoach([VIEC[0]], {"M1-ton-kho": {"xong": gio(6, 5, ngay=24).isoformat()}}, gio(13))
        self.assertEqual(len(kh["chay_bu"]), 1)

    def test_nhan_viec_tien_theo_ten(self):
        for ten in ["LENH-BANK-ALL", "tai so phu VCB", "Ngân hàng ACB", "thanh-toan-ncc", "PC-TAI CHINH"]:
            self.assertTrue(cb.la_viec_tien({"ten": ten}), ten)
        self.assertFalse(cb.la_viec_tien({"ten": "M1-ton-kho"}))


class ThucHien(unittest.TestCase):
    def setUp(self):
        self.kh = cb.lap_ke_hoach(VIEC, {}, gio(13, 46))
        self.goi = []

    def chay(self, lenh, gh):
        self.goi.append(lenh)
        return 0

    def test_chay_thu_khong_goi_lenh(self):
        tom = cb.thuc_hien(self.kh, {}, {"sql": lambda: True, "gmail": lambda: True}, chay_that=False,
                           bay_gio=lambda: gio(13, 47), doc_ram=lambda: 8000, chay=self.chay)
        self.assertEqual(self.goi, [])
        self.assertEqual(tom["chay_thu"], ["M1-ton-kho", "ban-tin-email"])

    def test_hong_quyen_gom_mot_lan(self):
        dem = {"n": 0}
        def gmail():
            dem["n"] += 1
            return False
        kh = {"chay_bu": [dict(VIEC[3], hen="x"), dict(VIEC[3], ten="email-2", hen="x")]}
        tom = cb.thuc_hien(kh, {}, {"gmail": gmail}, chay_that=True, bay_gio=lambda: gio(14),
                           doc_ram=lambda: 8000, chay=self.chay)
        self.assertEqual(dem["n"], 1)
        self.assertEqual(tom["hong_quyen"], {"gmail": ["ban-tin-email", "email-2"]})
        self.assertEqual(self.goi, [])

    def test_kiem_quyen_nem_loi_coi_nhu_hong(self):
        def hong():
            raise RuntimeError("token revoked")
        tom = cb.thuc_hien({"chay_bu": [dict(VIEC[3], hen="x")]}, {}, {"gmail": hong}, chay_that=True,
                           bay_gio=lambda: gio(14), doc_ram=lambda: 8000, chay=self.chay)
        self.assertIn("gmail", tom["hong_quyen"])

    def test_cua_ram(self):
        tom = cb.thuc_hien({"chay_bu": [dict(VIEC[0], hen="x")]}, {}, {"sql": lambda: True}, chay_that=True,
                           bay_gio=lambda: gio(14), doc_ram=lambda: 1200, chay=self.chay)
        self.assertEqual(tom["hoan_ram"], ["M1-ton-kho"])
        self.assertEqual(self.goi, [])

    def test_chay_that_ghi_trang_thai_va_bridge(self):
        tt = {}
        with tempfile.TemporaryDirectory() as d:
            ma = iter([0, 3])
            tom = cb.thuc_hien(self.kh, tt, {"sql": lambda: True, "gmail": lambda: True}, chay_that=True,
                               bay_gio=lambda: gio(13, 50), doc_ram=lambda: 8000,
                               chay=lambda l, g: next(ma), thu_muc_bridge=Path(d))
            tep = sorted(p.name for p in Path(d).iterdir())
            noi_dung = "".join(p.read_text(encoding="utf-8") for p in Path(d).iterdir())
        self.assertEqual(tom["xong"], ["M1-ton-kho"])
        self.assertEqual(tom["loi"], ["ban-tin-email"])
        self.assertIn("xong", tt["M1-ton-kho"])
        self.assertIn("loi", tt["ban-tin-email"])
        # bat-dau + kết quả cho mỗi việc; cùng phút thì tệp kết quả ghi đè tệp bat-dau.
        self.assertTrue(all(t.startswith("ket-qua-PC-H2-") for t in tep))
        self.assertIn("Mã thoát: 3", noi_dung)

    def test_viec_tien_khong_bao_gio_chay(self):
        tom = cb.thuc_hien(self.kh, {}, {"sql": lambda: True, "gmail": lambda: True}, chay_that=True,
                           bay_gio=lambda: gio(14), doc_ram=lambda: 8000, chay=self.chay)
        self.assertNotIn("LENH-BANK-ALL", tom["xong"] + tom["loi"])
        self.assertEqual(len(self.goi), 2)


class BaoCaoVaMain(unittest.TestCase):
    def test_bao_cao_va_ma_thoat(self):
        kh = cb.lap_ke_hoach(VIEC, {}, gio(13, 46))
        tom = {"xong": ["M1-ton-kho"], "loi": [], "hoan_ram": [], "hong_quyen": {}, "chay_thu": []}
        bc = cb.bao_cao(kh, tom, gio(14))
        self.assertIn("LENH-BANK-ALL", bc)
        self.assertIn("không tự chạy", bc)
        self.assertEqual(cb.ma_thoat(kh, tom), 2)
        self.assertEqual(cb.ma_thoat({"chi_bao_tien": [], "qua_cua_so": []}, dict(tom, loi=["a"])), 1)

    def test_main_chay_thu_khong_ghi_gi(self):
        with tempfile.TemporaryDirectory() as d:
            ch = {"thu_muc_trang_thai": d + "/tt", "thu_muc_bridge": d + "/br", "viec": VIEC,
                  "kiem_quyen": {}}
            p = Path(d) / "c.json"; p.write_text(json.dumps(ch), encoding="utf-8")
            ma = cb.main(["--config", str(p)])
            self.assertFalse((Path(d) / "tt" / cb.TEP_TRANG_THAI).exists())
            self.assertFalse((Path(d) / "br").exists())
        self.assertIn(ma, (0, 2))

    def test_main_chay_that_lenh_that(self):
        with tempfile.TemporaryDirectory() as d:
            viec = [{"ten": "thu-python", "lich": ["00:00"], "cua_so_gio": 24,
                     "lenh": [sys.executable, "-c", "pass"]}]
            ch = {"thu_muc_trang_thai": d + "/tt", "thu_muc_bridge": d + "/br", "viec": viec}
            p = Path(d) / "c.json"; p.write_text(json.dumps(ch), encoding="utf-8")
            self.assertEqual(cb.main(["--config", str(p), "--chay-that"]), 0)
            tt = json.loads((Path(d) / "tt" / cb.TEP_TRANG_THAI).read_text(encoding="utf-8"))
            self.assertIn("xong", tt["thu-python"])
            # Chạy lần 2: đã xong -> không chạy lại (idempotent).
            self.assertEqual(cb.main(["--config", str(p), "--chay-that"]), 0)
            tt2 = json.loads((Path(d) / "tt" / cb.TEP_TRANG_THAI).read_text(encoding="utf-8"))
            self.assertEqual(tt, tt2)

    def test_lenh_khong_ton_tai(self):
        self.assertEqual(cb.chay_lenh(["/khong/co/lenh-nay"], 5), 127)


if __name__ == "__main__":
    unittest.main()
