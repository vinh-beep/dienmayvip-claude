import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tong_hop_viec as th  # noqa: E402

NOW = datetime(2026, 10, 26, 20, 0, tzinfo=th.VN)


def w(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def tin(path, chu_de, ts, noi="việc", trang_thai="", tags=()):
    return w(path, json.dumps({"id": path.stem, "ts": ts, "type": "viec", "tags": list(tags), "from": "Cloud", "to": ["CC-QLVIP"],
                               "chu_de": chu_de, "trang_thai": trang_thai, "noiDung": [noi]}, ensure_ascii=False))


def md(path, tieu_de, than="", loai="viec", tags=(), ts="2026-10-26T10:00:00+07:00", chu_de=""):
    fm = f'---\nloai: {loai}\nid: {path.stem}\nts: {ts}\nnguon: "CC-QLVIP"\ntags: [{", ".join(chr(34)+t+chr(34) for t in tags)}]\ntieu_de: "{tieu_de}"\nchu_de: "{chu_de}"\n---\n'
    return w(path, fm + than)


@pytest.fixture
def kho(tmp_path):
    b = tmp_path / "bridge"
    tin(b / "tin-2026-10-26T07-52__viec__lenh1-5.json", "lenh1-5-cloud", "2026-10-26T07:52:00+07:00", "Lệnh 1-5", tags=["ai-team"])
    w(b / "ket-qua-CC-QLVIP-lenh1-5-cloud.json", json.dumps({"tu": "CC-QLVIP", "chu_de": "lenh1-5-cloud", "trang_thai": "chuyen-anh-Vinh",
                                                              "da_lam": "đã làm", "con_lai": "anh tạo nhánh main", "luc": "26/10/2026 11:28"}, ensure_ascii=False))
    tin(b / "tin-2026-10-26T08-00__viec__dong-bo-drive-loi.json", "dong-bo-drive-loi", "2026-10-26T08:00:00+07:00", "Quá 24 giờ chưa đẩy", tags=["canh-bao"])
    tin(b / "tin-2026-10-26T19-30__viec__moi.json", "viec-moi", "2026-10-26T19:30:00+07:00", "vừa gửi")
    v = tmp_path / "vault"
    md(v / "2026-10-26 🟡 Lazada chưa có accessToken.md", "🟡 Lazada chưa có accessToken app 120801", "anh mở D LAZADA", tags=["chủ-đề/marketing-mxh"])
    md(v / "2026-10-25 ⚠ 3 model đến hạn sell-in chưa có ParentSKU.md", "⚠ 3 model MỚI đến hạn sell-in nhưng CHƯA có ParentSKU", tags=["chủ-đề/giá-báo-giá"])
    md(v / "2026-10-26 ✅ CC Sync xong.md", "✅ 26 10 CC Sync xong 3 tinh hoa", tags=["chủ-đề/ai-claude"])
    md(v / "2026-10-25 Hộp Mail VIP KHÔNG đồng bộ.md", "25 10 23h Hộp Mail VIP (Lark Mail VIP) KHÔNG đồng bộ từ 22 10",
       "nap_mail.log invalid_grant. Liên hệ 0903750999. Số tài khoản 123456789012. Giá vốn A17 4.500.000", tags=["chủ-đề/tài-chính-ngân-hàng"])
    md(v / "2026-10-26 TINH HOA harness.md", "26 10 2026 TINH HOA (CC-QLVIP) — HARNESS² CHO APP", "luật", loai="tri-thuc", tags=["harness2"])
    w(v / "_done" / "cu.md", "---\ntieu_de: \"cũ\"\n---\n")
    return b, v


# ---------------------------------------------------------------- che


def test_che_sdt_stk_va_dong_gia_noi_bo():
    out = th.che("gọi 0903 750 999 hoặc +84 905123456\nSố tài khoản: 123456789012\nGiá vốn A17 4.500.000\ngiá lẻ 5.000.000")
    assert "0903" not in out and "905123456" not in out and "123456789012" not in out and "4.500.000" not in out
    assert "giá lẻ 5.000.000" in out and out.count("[che") == 4


# ---------------------------------------------------------------- phân loại


@pytest.mark.parametrize("tieu_de,than,want", [
    ("🔴 KHẨN sheet SSG", "", "gap"), ("Watcher bridge báo động", "", "gap"),
    ("🟡 đang làm móc", "", "dang-lam"), ("⚠ 3 model đến hạn", "", "canh-bao"),
    ("✅ xong AI Team", "", "xong"), ("Ghi chú thường", "", "khac"),
    ("Việc", "CHỜ ANH BẤM: tạo nhánh main", "cho-anh"),
])
def test_phan_loai_trang_thai(tieu_de, than, want):
    assert th.phan_loai_trang_thai(tieu_de, than) == want


def test_phan_loai_danh_muc_theo_tag_roi_tu_khoa():
    assert th.phan_loai_danh_muc("x", ["chủ-đề/tài-chính-ngân-hàng"]) == "tai-chinh"
    assert th.phan_loai_danh_muc("x", ["chủ-đề/kho-ảnh-media"]) == "video-mxh"
    assert th.phan_loai_danh_muc("Hộp Mail VIP không đồng bộ", []) == "email-chuong"
    assert th.phan_loai_danh_muc("3 model chưa có ParentSKU tồn", []) in ("gia-bg", "ton-kho")
    assert th.phan_loai_danh_muc("abc xyz", []) == "khac"


# ---------------------------------------------------------------- quét + nối


def test_quet_doc_du_loai_va_bo_done(kho):
    muc = th.quet([kho[0], kho[1]])
    assert {m.loai for m in muc} == {"tin", "ket-qua", "ghi-chu"}
    assert not any("_done" in m.tep for m in muc)
    assert len(muc) == 9


def test_noi_tin_voi_ket_qua_va_phat_hien_treo(kho):
    muc = th.noi_ket_qua(th.quet([kho[0], kho[1]]), bay_gio=NOW, treo_gio=6)
    by = {(m.loai, m.chu_de or m.id): m for m in muc}
    assert by[("tin", "lenh1-5-cloud")].trang_thai == "xong"          # có ket-qua
    assert by[("tin", "dong-bo-drive-loi")].trang_thai == "treo"      # 12 giờ chưa có kết quả
    assert by[("tin", "viec-moi")].trang_thai == "dang-lam"           # mới 30 phút, chưa có kết quả
    kq = next(m for m in muc if m.loai == "ket-qua")
    assert kq.trang_thai == "cho-anh"


def test_tri_thuc_khong_tinh_la_viec_mo(kho):
    muc = th.quet([kho[1]])
    assert next(m for m in muc if "TINH HOA" in m.tieu_de).trang_thai == "xong"


def test_tom_tat_da_che(kho):
    muc = th.quet([kho[1]])
    m = next(x for x in muc if "Hộp Mail" in x.tieu_de)
    assert "0903" not in m.tom_tat and "123456789012" not in m.tom_tat and "4.500.000" not in m.tom_tat


# ---------------------------------------------------------------- tổng kết + tệp ra


def test_chay_ghi_md_json_chep_index(kho, tmp_path):
    ra = tmp_path / "ra"
    kq = th.chay([kho[0], kho[1]], ra, bay_gio=NOW)
    assert kq["tong"] == 9 and kq["con_mo"] == 6 and kq["xong"] == 3
    md_text = (ra / "tong-hop-2026-10-26.md").read_text(encoding="utf-8")
    assert "## 🔥 Cần xử lý ngay" in md_text and "CHÉP TẤT CẢ" in md_text
    assert "Lazada" in md_text and "Hộp Mail VIP" in md_text
    chep = (ra / "chep-tat-ca.txt").read_text(encoding="utf-8")
    assert "CC Sync xong" not in chep and "Lazada" in chep and "0903" not in chep
    json.loads((ra / "tong-hop-2026-10-26.json").read_text(encoding="utf-8"))
    idx = (ra / "tong-hop-index.md").read_text(encoding="utf-8")
    assert "tong-hop-2026-10-26.md" in idx


def test_index_lien_ket_nhieu_ngay(kho, tmp_path):
    ra = tmp_path / "ra"
    th.chay([kho[0]], ra, bay_gio=NOW - timedelta(days=1))
    th.chay([kho[0]], ra, bay_gio=NOW)
    idx = (ra / "tong-hop-index.md").read_text(encoding="utf-8")
    assert idx.index("2026-10-26") < idx.index("2026-10-25")


def test_rong_khong_sap(tmp_path):
    kq = th.chay([tmp_path / "khong-co"], tmp_path / "ra", bay_gio=NOW)
    assert kq["tong"] == 0 and kq["ti_le_xong"] == 0


def test_json_hong_bi_bo_qua(tmp_path):
    w(tmp_path / "tin-2026-10-26T01-00__viec__x.json", "{hỏng")
    assert th.quet([tmp_path]) == []


def test_cli_khong_sap_khi_console_cp1252(kho, tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(Path(th.__file__)), "--nguon", str(kho[0]), "--nguon", str(kho[1]), "--ra", str(tmp_path / "r")],
                          capture_output=True, env=env, timeout=60)
    assert b"Traceback" not in proc.stderr, proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 0 and "còn mở".encode("utf-8") in proc.stdout
