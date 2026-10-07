import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dong_bo_drive as db  # noqa: E402
import kiem_an_toan as kat  # noqa: E402

NOW = time.time()
MAX = 50 * 1024 * 1024


def mk(root: Path, rel: str, data="x", age_s: float = 3600) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    os.utime(p, (NOW - age_s, NOW - age_s))
    return p


def scan(root, **kw):
    args = dict(max_size=MAX, max_age_s=2 * 86400, min_age_s=60, now=NOW)
    args.update(kw)
    return kat.quet_thu_muc(root, **args)


def xlsx(strings: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        body = "".join(f"<si><t>{s}</t></si>" for s in strings)
        z.writestr("xl/sharedStrings.xml", f"<sst>{body}</sst>")
        z.writestr("[Content_Types].xml", "<Types/>")
    return buf.getvalue()


# ---------------------------------------------------------------- loại trừ theo tên


def test_loai_tru_thu_muc_rac(tmp_path):
    for d in ["venv", ".venv", "site-packages", "torch", "node_modules", ".git", "__pycache__", "_Config"]:
        mk(tmp_path, f"{d}/a.txt")
    mk(tmp_path, "app/torch/include/x.txt")  # ở mọi cấp
    mk(tmp_path, "ok/ghi-chu.md", "xin chao")
    r = scan(tmp_path)
    assert r.allowed == ["ok/ghi-chu.md"]
    assert r.skipped["thu-muc-loai-tru"] == 9


def test_loai_tru_ten_tep(tmp_path):
    for n in ["~$bang.xlsx", "a.tmp", "a.pyc", "a.py.bak-20261005-2139", "m.py.bak-khonen-20261005", "x.log", "#ghi.txt", ";a.txt"]:
        mk(tmp_path, n)
    mk(tmp_path, "tot.txt", "tot")
    r = scan(tmp_path)
    assert r.allowed == ["tot.txt"]


@pytest.mark.parametrize("name", ["config.env", "tokens.json", "TOKEN-HUB.md", "gia_von.csv", "gmail_imap.txt", "ma.pem", "TKXT.md"])
def test_ten_nhay_cam_bi_chan(tmp_path, name):
    mk(tmp_path, name, "noi dung vo hai")
    r = scan(tmp_path)
    assert r.allowed == [] and r.blocked[name] == "ten-nhay-cam"


# ---------------------------------------------------------------- nội dung


@pytest.mark.parametrize("rel,data", [
    ("a.json", '{"api_key": "abcd1234efgh5678"}'),
    ("b.py", 'DB_PASSWORD = "hunter2hunter2"'),
    ("c.txt", "AIza" + "A" * 35),
    ("d.md", "-----BEGIN PRIVATE KEY-----\nabc"),
    ("e.json", '{"mật khẩu": "matkhau12345"}'),
    ("f.txt", "ghi chú\nAQ.Ab8" + "x" * 30),
])
def test_bi_mat_bi_chan_ca_trong_ma_nguon(tmp_path, rel, data):
    mk(tmp_path, rel, data)
    r = scan(tmp_path)
    assert rel in r.blocked and rel not in r.allowed


def test_khong_chan_nham_ma_nguon_lanh(tmp_path):
    mk(tmp_path, "ok1.py", 'password = os.environ["DMV_PW"]\nmax_tokens = 1000\ntoken_url = "https://example.com/oauth/token"\n')
    mk(tmp_path, "ok2.py", 'API_TOKEN = ""\nclient_secret = None\n')
    mk(tmp_path, "ok3.py", "SELECT GiaVon FROM x  # ten cot, khong phai du lieu\n")
    r = scan(tmp_path)
    assert sorted(r.allowed) == ["ok1.py", "ok2.py", "ok3.py"], r.blocked


@pytest.mark.parametrize("data", [
    "ParentSKU,Giá vốn,Giá lẻ\nA,1,2",
    "ParentSKU,NCC rẻ nhất (NỘI BỘ),Số NCC",
    "col: GiaSi_ReNhat",
    "Giá gợi ý VIP",
    "lien he 0905123456 gap anh Vinh",
    "SĐT 0905 123 456",
    "+84 905 123 456",
    "Số tài khoản: 1234567890",
    "CCCD 083123456789",
])
def test_du_lieu_nhay_cam_bi_chan(tmp_path, data):
    mk(tmp_path, "d.csv", data)
    r = scan(tmp_path)
    assert "d.csv" in r.blocked, data


def test_du_lieu_ban_hang_binh_thuong_di_qua(tmp_path):
    mk(tmp_path, "gia.csv", "ParentSKU,Ten,Ton,Gia le\nNOKIA 105 4G PRO,Nokia,716,780000\nA36,Samsung,3,7540000\n")
    r = scan(tmp_path)
    assert r.allowed == ["gia.csv"]


def test_log_khong_ghi_noi_dung_khop(tmp_path):
    mk(tmp_path, "x.json", '{"api_key": "SECRETVALUE12345"}')
    r = scan(tmp_path)
    assert "SECRETVALUE" not in json.dumps(r.blocked)
    assert r.blocked["x.json"].startswith("gan-mat-khau-token@")


# ---------------------------------------------------------------- loại tệp

def test_anh_di_qua_pdf_zip_va_loai_la_bi_chan(tmp_path):
    mk(tmp_path, "a.jpg", b"\xff\xd8binary")
    mk(tmp_path, "b.png", b"\x89PNG")
    mk(tmp_path, "c.pdf", b"%PDF-1.4 so tai khoan")
    mk(tmp_path, "d.zip", b"PK")
    mk(tmp_path, "e.dat", b"123")
    mk(tmp_path, "f.db", b"SQLite")
    r = scan(tmp_path)
    assert sorted(r.allowed) == ["a.jpg", "b.png"]
    assert set(r.blocked) == {"c.pdf", "d.zip", "e.dat", "f.db"}


def test_cho_phep_duoi_khong_quet_theo_cau_hinh(tmp_path):
    mk(tmp_path, "c.pdf", b"%PDF")
    assert scan(tmp_path, cho_phep_khong_quet=frozenset({".pdf"})).allowed == ["c.pdf"]


def test_xlsx_duoc_quet_noi_dung(tmp_path):
    mk(tmp_path, "xau.xlsx", xlsx(["ParentSKU", "Giá vốn", "NCC rẻ nhất"]))
    mk(tmp_path, "tot.xlsx", xlsx(["ParentSKU", "Giá lẻ", "Tồn"]))
    mk(tmp_path, "hong.xlsx", b"khong phai zip")
    r = scan(tmp_path)
    assert r.allowed == ["tot.xlsx"]
    assert r.blocked["xau.xlsx"].startswith("gia-von-ncc")
    assert r.blocked["hong.xlsx"].startswith("khong-doc-duoc-ooxml")


# ---------------------------------------------------------------- kích thước, tuổi, liên kết


def test_gioi_han_dung_luong_tuoi_va_dang_ghi_do(tmp_path):
    mk(tmp_path, "lon.txt", "a" * 2000)
    mk(tmp_path, "cu.txt", "cu", age_s=3 * 86400)
    mk(tmp_path, "moi-ghi.txt", "moi", age_s=5)
    mk(tmp_path, "ok.txt", "ok")
    r = scan(tmp_path, max_size=1000)
    assert r.allowed == ["ok.txt"]
    assert (r.skipped["qua-lon"], r.skipped["qua-cu"], r.skipped["dang-ghi-do"]) == (1, 1, 1)


def test_bo_qua_lien_ket(tmp_path):
    target = tmp_path / "ngoai"
    mk(target, "bi-mat.txt", "du lieu ngoai thu muc")
    root = tmp_path / "goc"
    mk(root, "a.txt")
    try:
        os.symlink(target, root / "lien-ket", target_is_directory=True)
        os.symlink(target / "bi-mat.txt", root / "tep-lien-ket.txt")
    except OSError:
        pytest.skip("không tạo được symlink")
    r = scan(root)
    assert r.allowed == ["a.txt"]


# ---------------------------------------------------------------- cấu hình


def cfg_file(tmp_path, **override):
    cfg = {
        "remote": "dmv-drive:",
        "nguon": [{"thu_muc": str(tmp_path / "src"), "dich": "Nguon"}],
        "thu_muc_log": str(tmp_path / "log"),
    }
    cfg.update(override)
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def test_cau_hinh_hop_le_co_mac_dinh(tmp_path):
    cfg = db.load_config(cfg_file(tmp_path))
    assert cfg["max_size"] == "50M" and cfg["max_age"] == "2d" and cfg["bao_loi_sau_gio"] == 24


@pytest.mark.parametrize("nguon", [
    [{"thu_muc": "C:\\", "dich": "x"}],
    [{"thu_muc": "D:/", "dich": "x"}],
    [{"thu_muc": "C:\\Users\\Win10\\Desktop", "dich": "x"}],
    [{"thu_muc": "C:\\ClaudeVIP", "dich": "a/b"}],
    [{"thu_muc": "C:\\ClaudeVIP", "dich": ".."}],
    [{"thu_muc": "C:\\ClaudeVIP"}],
])
def test_cau_hinh_nguy_hiem_bi_tu_choi(tmp_path, nguon):
    with pytest.raises(db.ConfigError):
        db.load_config(cfg_file(tmp_path, nguon=nguon))


def test_remote_phai_ket_thuc_bang_hai_cham(tmp_path):
    with pytest.raises(db.ConfigError):
        db.load_config(cfg_file(tmp_path, remote="dmv-drive"))


def test_doc_dung_luong_va_thoi_gian():
    assert db.parse_size("50M") == 50 * 1024**2 and db.parse_size("1G") == 1024**3
    assert db.parse_age("2d") == 172800 and db.parse_age("30m") == 1800
    for bad in ["abc", "5x", ""]:
        with pytest.raises(db.ConfigError):
            db.parse_size(bad) if bad != "5x" else db.parse_age(bad)


def test_lenh_rclone_chi_copy_khong_xoa(tmp_path):
    cfg = db.load_config(cfg_file(tmp_path))
    for chay_that in (False, True):
        cmd = db.build_rclone_cmd(cfg, "C:\\src", "Nguon", Path("l.txt"), Path("r.log"), chay_that=chay_that)
        assert cmd[:2] == [cfg["rclone"], "copy"]
        assert not {"sync", "move", "delete", "purge", "--delete-after", "--delete-during"} & set(cmd)
        assert ("--dry-run" in cmd) is (not chay_that)
        assert cmd[cmd.index("--max-size") + 1] == "50M"
        assert "--files-from" in cmd


# ---------------------------------------------------------------- chạy đồng bộ


class FakeRunner:
    def __init__(self, code=0, exc=None):
        self.calls, self.code, self.exc = [], code, exc

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if self.exc:
            raise self.exc
        return SimpleNamespace(returncode=self.code, stdout="", stderr="")


def setup_src(tmp_path):
    src = tmp_path / "src"
    mk(src, "tot.md", "noi dung tot")
    mk(src, "venv/rac.txt")
    mk(src, "bimat.json", '{"api_key": "abcd1234efgh5678"}')
    mk(src, "anh/a.jpg", b"\xff\xd8")
    return db.load_config(cfg_file(tmp_path))


def test_chay_thu_khong_ghi_thanh_cong(tmp_path):
    cfg = setup_src(tmp_path)
    runner = FakeRunner()
    st = db.chay_dong_bo(cfg, chay_that=False, now=NOW, runner=runner)
    assert st["che_do"] == "chay-thu" and st["ket_qua"] == "ok"
    assert st["lan_thanh_cong_cuoi"] is None
    assert "--dry-run" in runner.calls[0] and len(runner.calls) == 1  # không copyto trạng thái
    e = st["thu_muc"][0]
    assert (e["tim_thay"], e["se_day"], e["bi_chan"]) == (3, 2, 1)
    files_from = (tmp_path / "log" / "files-from-Nguon.txt").read_text(encoding="utf-8").split()
    assert sorted(files_from) == ["anh/a.jpg", "tot.md"]


def test_chay_that_thanh_cong_ghi_moc_va_day_trang_thai(tmp_path):
    cfg = setup_src(tmp_path)
    runner = FakeRunner()
    st = db.chay_dong_bo(cfg, chay_that=True, now=NOW, runner=runner)
    assert st["lan_thanh_cong_cuoi"] == st["ts"]
    assert runner.calls[0][1] == "copy" and "--dry-run" not in runner.calls[0]
    assert runner.calls[1][1] == "copyto" and runner.calls[1][-1].endswith("trang-thai-dong-bo.json")
    saved = json.loads((tmp_path / "log" / db.STATUS_NAME).read_text(encoding="utf-8"))
    assert saved["lan_thanh_cong_cuoi"] == st["ts"]


def test_trang_thai_khong_lo_ten_tep_hay_noi_dung(tmp_path):
    cfg = setup_src(tmp_path)
    db.chay_dong_bo(cfg, chay_that=True, now=NOW, runner=FakeRunner())
    text = (tmp_path / "log" / db.STATUS_NAME).read_text(encoding="utf-8")
    assert "bimat.json" not in text and "abcd1234" not in text
    assert "gan-mat-khau-token" in text
    chan = next((tmp_path / "log").glob("chan-*.txt")).read_text(encoding="utf-8")
    assert "Nguon/bimat.json\tgan-mat-khau-token@" in chan and "abcd1234" not in chan


@pytest.mark.parametrize("runner,expect", [
    (FakeRunner(code=1), "mã 1"),
    (FakeRunner(exc=FileNotFoundError()), "Không tìm thấy rclone"),
])
def test_loi_rclone_khong_ghi_moc_thanh_cong(tmp_path, runner, expect):
    cfg = setup_src(tmp_path)
    st = db.chay_dong_bo(cfg, chay_that=True, now=NOW, runner=runner)
    assert st["ket_qua"] == "loi" and expect in " ".join(st["loi"])
    assert st["lan_thanh_cong_cuoi"] is None
    assert len(runner.calls) == 1  # không đẩy trạng thái khi lỗi


def test_loi_khong_xoa_moc_thanh_cong_cu(tmp_path):
    cfg = setup_src(tmp_path)
    db.chay_dong_bo(cfg, chay_that=True, now=NOW, runner=FakeRunner())
    st = db.chay_dong_bo(cfg, chay_that=True, now=NOW + 10, runner=FakeRunner(code=1))
    assert st["ket_qua"] == "loi" and st["lan_thanh_cong_cuoi"] is not None


def test_thieu_thu_muc_nguon_la_loi(tmp_path):
    cfg = setup_src(tmp_path)
    cfg["nguon"][0]["thu_muc"] = str(tmp_path / "khong-co")
    st = db.chay_dong_bo(cfg, chay_that=False, now=NOW, runner=FakeRunner())
    assert st["ket_qua"] == "loi"


def test_khoa_chong_chay_chong(tmp_path):
    cfg = setup_src(tmp_path)
    lock = tmp_path / "log"
    lock.mkdir(exist_ok=True)
    with db.Lock(lock / "dong-bo.lock"):
        with pytest.raises(RuntimeError):
            db.chay_dong_bo(cfg, chay_that=False, now=NOW, runner=FakeRunner())
    db.chay_dong_bo(cfg, chay_that=False, now=NOW, runner=FakeRunner())  # nhả khóa thì chạy được


# ---------------------------------------------------------------- báo quá hạn


def status_with_last(tmp_path, last_iso):
    log = tmp_path / "log"
    log.mkdir(exist_ok=True)
    (log / db.STATUS_NAME).write_text(json.dumps({"lan_thanh_cong_cuoi": last_iso}), encoding="utf-8")


def test_kiem_tuoi_con_han(tmp_path):
    cfg = db.load_config(cfg_file(tmp_path))
    status_with_last(tmp_path, db._now_vn(NOW - 3600).isoformat())
    ok, _ = db.kiem_tuoi(cfg, now=NOW)
    assert ok


def test_kiem_tuoi_qua_han_ghi_dung_mot_tin_moi_24_gio(tmp_path):
    tin = tmp_path / "bridge"
    tin.mkdir()
    cfg = db.load_config(cfg_file(tmp_path, thu_muc_tin=str(tin)))
    status_with_last(tmp_path, db._now_vn(NOW - 30 * 3600).isoformat())
    ok, msg = db.kiem_tuoi(cfg, now=NOW)
    assert not ok and "Quá 24 giờ" in msg
    files = list(tin.glob("tin-*__viec__dong-bo-drive-loi.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["type"] == "viec" and data["to"] == ["CC-QLVIP"] and data["chu_de"] == "dong-bo-drive-loi"
    db.kiem_tuoi(cfg, now=NOW + 3600)  # chưa đủ 24 giờ → không tin mới
    assert len(list(tin.glob("tin-*.json"))) == 1
    db.kiem_tuoi(cfg, now=NOW + 25 * 3600)
    assert len(list(tin.glob("tin-*.json"))) == 2


def test_kiem_tuoi_chua_tung_chay(tmp_path):
    cfg = db.load_config(cfg_file(tmp_path))
    ok, msg = db.kiem_tuoi(cfg, now=NOW)
    assert not ok and "Chưa có" in msg


def test_main_ma_thoat(tmp_path, capsys):
    cfgp = cfg_file(tmp_path)
    assert db.main(["--config", str(cfgp), "--kiem-tuoi"]) == 2
    assert db.main(["--config", str(tmp_path / "khong-co.json")]) == 1
