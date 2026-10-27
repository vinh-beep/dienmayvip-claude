"""Kiểm thử Harness² vòng 2 cho bộ chặn (hoc_tu_chan.py) và phần nối vào vòng 1."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dong_bo_drive as db  # noqa: E402
import hoc_tu_chan as h2  # noqa: E402
import kiem_an_toan as kat  # noqa: E402

NOW = time.time()
MAX = 50 * 1024 * 1024
PDF = b"%PDF-1.4 noi dung lanh"
SDT = "lien he 0905123456 gap anh Vinh\n"
KEY = "AIza" + "A" * 35


def mk(root: Path, rel: str, data="x", age_s: float = 3600) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    os.utime(p, (NOW - age_s, NOW - age_s))
    return p


def sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def scan(root, **kw):
    args = dict(max_size=MAX, max_age_s=2 * 86400, min_age_s=60, now=NOW)
    args.update(kw)
    return kat.quet_thu_muc(root, **args)


def cfg_for(tmp_path) -> dict:
    cfg = {
        "remote": "dmv-drive:",
        "nguon": [{"thu_muc": str(tmp_path / "src"), "dich": "BaoCao"}],
        "thu_muc_log": str(tmp_path / "log"),
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return db.load_config(p)


class FakeRunner:
    def __init__(self, code=0):
        self.code, self.calls = code, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=self.code, stdout="", stderr="")


# ---------------------------------------------------------------- luật cứng / mềm


def test_luat_cung_mem_tach_biet_va_du():
    assert kat.LUAT_CUNG.isdisjoint(kat.LUAT_MEM)
    for name, _ in kat.SECRET_RULES:
        assert name in kat.LUAT_CUNG
    for name in ("gia-von-ncc", "cccd-cmnd", "ten-nhay-cam"):
        assert name in kat.LUAT_CUNG
    for name in ("so-dien-thoai-vn", "loai-tep-khong-quet-duoc"):
        assert name in kat.LUAT_MEM


def test_kiem_nhanh_dat():
    assert h2.kiem_nhanh() == []


# ---------------------------------------------------------------- vòng 1 nhận bài học


def test_tep_oan_luat_mem_di_qua_khi_sha_khop(tmp_path):
    mk(tmp_path, "a.pdf", PDF)
    r0 = scan(tmp_path)
    assert r0.blocked["a.pdf"] == "loai-tep-khong-quet-duoc"
    r = scan(tmp_path, cho_phep_tep={"a.pdf": sha(PDF)})
    assert r.allowed == ["a.pdf"] and r.theo_bai_hoc == ["a.pdf"] and not r.blocked


def test_tep_oan_doi_noi_dung_thi_chan_lai(tmp_path):
    mk(tmp_path, "a.pdf", PDF + b" them")
    r = scan(tmp_path, cho_phep_tep={"a.pdf": sha(PDF)})
    assert r.blocked["a.pdf"] == "loai-tep-khong-quet-duoc" and r.theo_bai_hoc == []


def test_luat_cung_khong_nhan_ngoai_le_du_co_sha(tmp_path):
    mk(tmp_path, "k.txt", KEY)
    mk(tmp_path, "gia.csv", "ParentSKU,gia_von\nA,1\n")
    mk(tmp_path, "TOKEN-HUB.md", "lanh")
    allow = {"k.txt": sha(KEY), "gia.csv": sha("ParentSKU,gia_von\nA,1\n"), "TOKEN-HUB.md": sha("lanh")}
    r = scan(tmp_path, cho_phep_tep=allow)
    assert r.allowed == [] and len(r.blocked) == 3 and r.theo_bai_hoc == []


def test_sdt_oan_di_qua_nhung_bi_mat_trong_cung_tep_van_chan(tmp_path):
    mk(tmp_path, "sdt.txt", SDT)
    mk(tmp_path, "sdt-va-khoa.txt", SDT + KEY)  # luật bí mật đứng trước luật dữ liệu
    allow = {"sdt.txt": sha(SDT), "sdt-va-khoa.txt": sha(SDT + KEY)}
    r = scan(tmp_path, cho_phep_tep=allow)
    assert r.allowed == ["sdt.txt"]
    assert r.blocked["sdt-va-khoa.txt"].startswith("khoa-api-google")


# ---------------------------------------------------------------- đọc log vòng 1


def test_doc_chan_logs_gom_theo_tep(tmp_path):
    (tmp_path / "chan-1.txt").write_text("BaoCao/a.pdf\tloai-tep-khong-quet-duoc\nBaoCao/b.csv\tso-dien-thoai-vn@3\ndong hong\n", encoding="utf-8")
    (tmp_path / "chan-2.txt").write_text("BaoCao/a.pdf\tloai-tep-khong-quet-duoc\n", encoding="utf-8")
    chan = h2.doc_chan_logs(tmp_path)
    assert chan["BaoCao/a.pdf"] == {"luat": "loai-tep-khong-quet-duoc", "lan": 2, "cuoi": "chan-2.txt"}
    assert chan["BaoCao/b.csv"]["luat"] == "so-dien-thoai-vn" and chan["BaoCao/b.csv"]["lan"] == 1
    assert "dong hong" not in chan


# ---------------------------------------------------------------- tổng hợp (thuần hàm)


def test_duoi_5_mau_chua_du_du_lieu():
    chan = {f"B/{i}.pdf": {"luat": "loai-tep-khong-quet-duoc", "lan": 1, "cuoi": "c"} for i in range(4)}
    px = {k: {"ket_luan": "oan", "ts": "t", "sha256": "a" * 64} for k in chan}
    t = h2.tong_hop(chan, px)
    r = t["luat"]["loai-tep-khong-quet-duoc"]
    assert r["phan_xu"] == 4 and r["ty_le_oan"] is None and "chưa đủ dữ liệu" in r["do_tin"]
    assert t["de_xuat"] == []  # không kết luận sớm
    assert len(t["cho_phep_tep"]) == 4  # nhưng từng tệp anh đã phán vẫn được qua


def test_du_5_mau_ra_ti_le_va_de_xuat_chi_de_xuat():
    chan = {f"B/{i}.csv": {"luat": "so-dien-thoai-vn", "lan": 1, "cuoi": "c"} for i in range(6)}
    px = {k: {"ket_luan": "oan" if i < 4 else "dung", "ts": "t", "sha256": "a" * 64} for i, k in enumerate(chan)}
    t = h2.tong_hop(chan, px)
    r = t["luat"]["so-dien-thoai-vn"]
    assert r["ty_le_oan"] == pytest.approx(4 / 6, abs=1e-3) and r["do_tin"] == "đủ mẫu"
    assert len(t["de_xuat"]) == 1 and "KHÔNG tự nới" in t["de_xuat"][0]
    assert len(t["cho_phep_tep"]) == 4  # chỉ tệp phán oan


def test_luat_cung_phan_oan_bi_bo_qua_va_ghi_nhan():
    chan = {f"B/{i}.txt": {"luat": "khoa-api-google", "lan": 1, "cuoi": "c"} for i in range(5)}
    px = {k: {"ket_luan": "oan", "ts": "t", "sha256": "a" * 64} for k in chan}
    t = h2.tong_hop(chan, px)
    assert t["cho_phep_tep"] == {} and len(t["bo_qua_vi_luat_cung"]) == 5
    assert any("CỨNG" in d and "giữ chặn" in d for d in t["de_xuat"])


def test_oan_khong_co_sha_thi_khong_cho_qua():
    chan = {"B/a.pdf": {"luat": "loai-tep-khong-quet-duoc", "lan": 1, "cuoi": "c"}}
    px = {"B/a.pdf": {"ket_luan": "oan", "ts": "t", "canh_bao": "khong-thay-tep-khi-phan-xu"}}
    assert h2.tong_hop(chan, px)["cho_phep_tep"] == {}


# ---------------------------------------------------------------- ghi phán xử + vòng khép kín


def test_them_phan_xu_bam_sha_va_tu_choi_dau_vao_xau(tmp_path):
    cfg = cfg_for(tmp_path)
    mk(tmp_path / "src", "a.pdf", PDF)
    px = h2.them_phan_xu(cfg, ["BaoCao/a.pdf=oan", "BaoCao\\b.csv=dung", "BaoCao/mat.pdf=oan"], now=NOW)
    assert px["BaoCao/a.pdf"]["sha256"] == sha(PDF)
    assert px["BaoCao/b.csv"]["ket_luan"] == "dung" and "sha256" not in px["BaoCao/b.csv"]
    assert px["BaoCao/mat.pdf"]["canh_bao"] == "khong-thay-tep-khi-phan-xu"
    saved = json.loads((tmp_path / "log" / h2.PHAN_XU_NAME).read_text(encoding="utf-8"))
    assert set(saved["phan_xu"]) == {"BaoCao/a.pdf", "BaoCao/b.csv", "BaoCao/mat.pdf"}
    for bad in (["BaoCao/a.pdf"], ["BaoCao/a.pdf=sai"], ["a.pdf=oan"], ["BaoCao/../cfg.json=oan"]):
        with pytest.raises(h2.DauVaoLoi):
            h2.them_phan_xu(cfg, bad, now=NOW)


def test_phan_xu_lan_sau_ghi_de_khong_xoa_cu(tmp_path):
    cfg = cfg_for(tmp_path)
    mk(tmp_path / "src", "a.pdf", PDF)
    h2.them_phan_xu(cfg, ["BaoCao/a.pdf=oan"], now=NOW)
    px = h2.them_phan_xu(cfg, ["BaoCao/x.csv=dung"], now=NOW + 1)
    assert set(px) == {"BaoCao/a.pdf", "BaoCao/x.csv"}
    px = h2.them_phan_xu(cfg, ["BaoCao/a.pdf=dung"], now=NOW + 2)
    assert px["BaoCao/a.pdf"]["ket_luan"] == "dung" and "sha256" not in px["BaoCao/a.pdf"]


def test_vong_khep_kin_chan_roi_phan_oan_roi_qua(tmp_path):
    """Vòng 1 chặn → anh phán oan → vòng 2 sinh sổ → vòng 1 lần sau cho qua đúng tệp đó, tệp khác vẫn chặn."""
    cfg = cfg_for(tmp_path)
    src = tmp_path / "src"
    mk(src, "bao-cao.pdf", PDF)
    mk(src, "khac.pdf", b"%PDF khac")
    mk(src, "khoa.txt", KEY)
    st1 = db.chay_dong_bo(cfg, chay_that=False, now=NOW, runner=FakeRunner())
    assert st1["thu_muc"][0]["bi_chan"] == 3 and st1["thu_muc"][0]["theo_bai_hoc"] == 0

    h2.them_phan_xu(cfg, ["BaoCao/bao-cao.pdf=oan", "BaoCao/khoa.txt=oan"], now=NOW)
    tong = h2.chay_vong_2(cfg, now=NOW)
    assert tong["cho_phep_tep"] == {"BaoCao/bao-cao.pdf": sha(PDF)}
    assert tong["bo_qua_vi_luat_cung"] == ["BaoCao/khoa.txt"]
    assert tong["chua_phan_xu"] == ["BaoCao/khac.pdf"]

    runner = FakeRunner()
    st2 = db.chay_dong_bo(cfg, chay_that=False, now=NOW + 5, runner=runner)
    e = st2["thu_muc"][0]
    assert e["se_day"] == 1 and e["bi_chan"] == 2 and e["theo_bai_hoc"] == 1
    files_from = (tmp_path / "log" / "files-from-BaoCao.txt").read_text(encoding="utf-8").split()
    assert files_from == ["bao-cao.pdf"]

    # đổi nội dung tệp đã phán oan → chặn lại
    mk(src, "bao-cao.pdf", PDF + b" sua")
    st3 = db.chay_dong_bo(cfg, chay_that=False, now=NOW + 10, runner=FakeRunner())
    assert st3["thu_muc"][0]["theo_bai_hoc"] == 0 and st3["thu_muc"][0]["bi_chan"] == 3


def test_so_bai_hoc_md_moi_nhat_tren_cung_va_khong_lo_noi_dung(tmp_path):
    cfg = cfg_for(tmp_path)
    src = tmp_path / "src"
    mk(src, "sdt.csv", SDT)
    mk(src, "k.txt", KEY)
    db.chay_dong_bo(cfg, chay_that=False, now=NOW, runner=FakeRunner())
    h2.them_phan_xu(cfg, ["BaoCao/sdt.csv=oan"], now=NOW)
    h2.them_phan_xu(cfg, ["BaoCao/k.txt=dung"], now=NOW + 60)
    h2.chay_vong_2(cfg, now=NOW + 120)
    md = (tmp_path / "log" / h2.BAI_HOC_MD).read_text(encoding="utf-8")
    assert "0905123456" not in md and KEY not in md  # không lộ nội dung khớp
    assert "chưa đủ dữ liệu" in md
    i_k, i_sdt = md.index("| BaoCao/k.txt |"), md.index("| BaoCao/sdt.csv |")
    assert i_k < i_sdt  # phán xử mới hơn đứng trên
    js = json.loads((tmp_path / "log" / h2.BAI_HOC_JSON).read_text(encoding="utf-8"))
    assert js["cho_phep_tep"] == {"BaoCao/sdt.csv": sha(SDT)} and js["mau_toi_thieu"] == 5


def test_bai_hoc_hong_thi_khong_noi_gi(tmp_path):
    (tmp_path / "x.json").write_text("{hong", encoding="utf-8")
    assert db.doc_cho_phep_tep(tmp_path / "x.json") == {}
    (tmp_path / "y.json").write_text(json.dumps({"cho_phep_tep": {"a": "ngan", "b": 5, "c": "f" * 64}}), encoding="utf-8")
    assert db.doc_cho_phep_tep(tmp_path / "y.json") == {"c": "f" * 64}
    assert db.doc_cho_phep_tep(tmp_path / "khong-co.json") == {}


def test_main_ma_thoat(tmp_path, capsys):
    assert h2.main(["--kiem"]) == 0
    assert h2.main([]) == 1
    cfg_for(tmp_path)
    assert h2.main(["--config", str(tmp_path / "cfg.json"), "--phan-xu", "BaoCao/a.pdf=xau"]) == 1
    assert h2.main(["--config", str(tmp_path / "cfg.json")]) == 0
    out = capsys.readouterr().out
    assert "Sổ bài học" in out and (tmp_path / "log" / h2.BAI_HOC_MD).is_file()
