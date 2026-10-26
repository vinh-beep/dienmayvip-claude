import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tong_ket as tk  # noqa: E402

LUC = datetime(2026, 10, 26, 19, 30, tzinfo=tk.VN)


def tin(ten, **d):
    goc = {"id": ten, "type": "tin", "from": "TrangThaiHeThong", "to": ["Vinh"], "chu_de": "trang-thai-he-thong",
           "noiDung": [], "can_xac_nhan": False}
    goc.update(d)
    return ten + ".json", json.dumps(goc, ensure_ascii=False)


MAU = [
    tin("tin-2026-10-26T19-01__tin__trang-thai-he-thong",
        noiDung=["TRẠNG THÁI 26/10 19:01 — 1 cảnh báo. 15 tác vụ lỗi: DMV ChatAI Service (ma 1073807364); DMV DongBo Service (ma 267014)"]),
    tin("tin-2026-10-26T10-36__tin__trang-thai-he-thong", noiDung=["TRẠNG THÁI 26/10 10:36 — 0 cảnh báo."]),
    tin("tin-2026-10-26T11-28__viec__cc-lang-nghe-can-anh", type="viec", **{"from": "CC-QLVIP"}, chu_de="cc-lang-nghe-can-anh",
        can_xac_nhan=True, noiDung=["Anh chạy gmail-cap-lai-quyen.py, gọi 0912345678 hoặc mail vinh@dienmayvip.com, STK 123456789"]),
    tin("tin-2026-10-26T11-29__viec__cc-lang-nghe-can-anh", type="viec", **{"from": "CC-QLVIP"}, chu_de="cc-lang-nghe-can-anh",
        can_xac_nhan=True, noiDung=["Anh chạy gmail-cap-lai-quyen.py, gọi 0912345678 hoặc mail vinh@dienmayvip.com, STK 123456789 (gửi lại)"]),
    ("luat-2026-10-26-tu-chay.json", json.dumps({"loai": "luat", "id": "luat-tu-chay", "tu": "Cloud", "noi_dung": ["1. Tự làm trọn."]})),
    ("ket-qua-CC-QLVIP-lenh1-5.json", json.dumps({"tu": "CC-QLVIP", "chu_de": "lenh1-5", "trang_thai": "chuyen-anh-Vinh",
                                                  "da_lam": "Đã quét PC", "con_lai": "Anh bật trigger Apps Script", "luc": "26/10/2026 11:28"})),
    ("ket-qua-PC-Harness2-Gia-San-26 10 2026 09h00p.md", "# Kết quả PC\n## ① Đã dựng — ĐẠT\n- test 8/8\n## ③ Giao PC\n- Chạy lại lịch 21h40\n"),
    ("tin-2026-10-24T08-00__tin__trang-thai-he-thong.json", json.dumps({"from": "X", "noiDung": ["cũ quá 24 giờ"], "chu_de": "trang-thai-he-thong"})),
    ("rac.txt", "không đọc"),
    ("ket-qua-hong.json", "{không phải json"),
]


class TongKet(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.b = Path(self.d.name)
        for ten, nd in MAU:
            (self.b / ten).write_text(nd, encoding="utf-8")
        self.ra = tk.gom(self.b, LUC, 24)

    def tearDown(self):
        self.d.cleanup()

    def test_phan_loai(self):
        ten = {k: [m["tep"] for m in v] for k, v in self.ra.items()}
        self.assertIn("tin-2026-10-26T19-01__tin__trang-thai-he-thong.json", ten["LOI"])
        self.assertIn("tin-2026-10-26T10-36__tin__trang-thai-he-thong.json", ten["XONG"])
        self.assertIn("ket-qua-CC-QLVIP-lenh1-5.json", ten["GAP"])
        self.assertIn("ket-qua-PC-Harness2-Gia-San-26 10 2026 09h00p.md", ten["GAP"])
        self.assertEqual(ten["LUAT"], ["luat-2026-10-26-tu-chay.json"])

    def test_loai_trung_giu_moi_nhat(self):
        gap = [m for m in self.ra["GAP"] if "cc-lang-nghe" in m["chu_de"]]
        self.assertEqual(len(gap), 1)
        self.assertEqual(gap[0]["tep"], "tin-2026-10-26T11-29__viec__cc-lang-nghe-can-anh.json")

    def test_che_pii(self):
        nd = " ".join(m["noi_dung"] for v in self.ra.values() for m in v)
        for cam in ("0912345678", "vinh@dienmayvip.com", "123456789"):
            self.assertNotIn(cam, nd)
        self.assertIn("[SĐT]", nd); self.assertIn("[email]", nd)

    def test_gan_cach_chua(self):
        loi = next(m for m in self.ra["LOI"])
        self.assertTrue(any("1073807364" in c for c in loi["chua"]))
        self.assertTrue(any("267014" in c for c in loi["chua"]))

    def test_bo_tep_cu_va_rac(self):
        tep = [m["tep"] for v in self.ra.values() for m in v]
        self.assertNotIn("tin-2026-10-24T08-00__tin__trang-thai-he-thong.json", tep)
        self.assertNotIn("rac.txt", tep); self.assertNotIn("ket-qua-hong.json", tep)

    def test_md_co_khoi_sao_chep(self):
        md = tk.viet_md(self.ra, LUC, 24)
        self.assertIn("## KHỐI SAO CHÉP TOÀN BỘ", md)
        self.assertIn("1. 26/10", md)
        self.assertIn("🔧 1073807364", md)

    def test_main_idempotent(self):
        ra_dir = self.b / "ra"
        tk.main(["--bridge", str(self.b), "--ra", str(ra_dir), "--luc", LUC.isoformat()])
        a = (ra_dir / "TONG-KET-TU-DONG-moi-nhat.md").read_text(encoding="utf-8")
        tk.main(["--bridge", str(self.b), "--ra", str(ra_dir), "--luc", LUC.isoformat()])
        b = (ra_dir / "TONG-KET-TU-DONG-moi-nhat.md").read_text(encoding="utf-8")
        self.assertEqual(a, b)
        self.assertTrue((ra_dir / "TONG-KET-TU-DONG-26 10 2026 19h30p.md").exists())
        js = json.loads((ra_dir / "TONG-KET-TU-DONG-moi-nhat.json").read_text(encoding="utf-8"))
        self.assertEqual(set(js), {"GAP", "LOI", "XONG", "LUAT", "KHAC"})

    def test_khong_doc_lai_chinh_no(self):
        (self.b / "TONG-KET-TU-DONG-moi-nhat.md").write_text("# cũ", encoding="utf-8")
        ra = tk.gom(self.b, LUC, 24)
        self.assertNotIn("TONG-KET-TU-DONG-moi-nhat.md", [m["tep"] for v in ra.values() for m in v])


if __name__ == "__main__":
    unittest.main()
