import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kiem_chuan_app as kc  # noqa: E402


def mk_app(root: Path, name: str, *, kiem=True, help_md=True, secret=False, loi_cu=False):
    d = root / name
    d.mkdir(parents=True)
    code = 'import logging\nlogging.basicConfig(filename="app.log")\n'
    if kiem:
        code += 'if "--kiem" in sys.argv: pass\n'
    code += 'json.dump({}, open("trang-thai.json","w"))\n'
    if secret:
        code += 'API_KEY = "AIza' + "A" * 35 + '"\n'
    code += 'pw = os.environ["PW"]\nTOKEN_URL = "https://x/token"\n'
    (d / "app.py").write_text(code, encoding="utf-8")
    if help_md:
        (d / "HELP.md").write_text("# help", encoding="utf-8")
    (d / "KIEN-THUC-APP.md").write_text("x", encoding="utf-8")
    (d / "app.py.bak-20261026").write_text("x", encoding="utf-8")
    if loi_cu:
        (d / "loi.log").write_text("Traceback", encoding="utf-8")
        old = time.time() - 3600
        os.utime(d / "loi.log", (old, old))
    return d


def test_app_dat_chuan(tmp_path):
    a = kc.kiem_app(mk_app(tmp_path, "ok"))
    assert all(a.ket_qua.values()) and a.hong_bat_buoc == []


def test_app_thieu_kiem_va_help(tmp_path):
    a = kc.kiem_app(mk_app(tmp_path, "thieu", kiem=False, help_md=False))
    assert set(a.hong_bat_buoc) == {"kiem", "help"}


def test_bi_mat_gan_cung_bi_bat_nhung_env_thi_khong(tmp_path):
    a = kc.kiem_app(mk_app(tmp_path, "secret", secret=True))
    assert "bi-mat" in a.hong_bat_buoc
    assert kc.co_bi_mat_gan_cung('password = os.getenv("X")\ntoken_url = "https://a/token"') is False
    assert kc.co_bi_mat_gan_cung('password = "<DIEN-VAO>"') is False
    assert kc.co_bi_mat_gan_cung('password = "hunter2hunter2"') is True


def test_loi_cu_hon_ma_duoc_ghi_chu(tmp_path):
    a = kc.kiem_app(mk_app(tmp_path, "loi", loi_cu=True))
    assert any("cũ hơn" in g for g in a.ghi_chu)


def test_tim_app_bo_thu_muc_rac_va_khong_co_py(tmp_path):
    mk_app(tmp_path, "A")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "x.py").write_text("", encoding="utf-8")
    (tmp_path / "_Shared").mkdir()
    (tmp_path / "_Shared" / "y.py").write_text("", encoding="utf-8")
    (tmp_path / "chi-txt").mkdir()
    (tmp_path / "chi-txt" / "a.txt").write_text("", encoding="utf-8")
    assert [d.name for d in kc.tim_app([tmp_path])] == ["A"]


def test_main_ghi_tep_va_ma_thoat(tmp_path):
    mk_app(tmp_path / "goc", "ok")
    mk_app(tmp_path / "goc", "hong", kiem=False)
    rc = kc.main(["--goc", str(tmp_path / "goc"), "--ra", str(tmp_path / "ra")])
    assert rc == 1
    data = json.loads((tmp_path / "ra" / "chuan-app.json").read_text(encoding="utf-8"))
    assert {a["ten"] for a in data} == {"ok", "hong"}
    md = (tmp_path / "ra" / "chuan-app.md").read_text(encoding="utf-8")
    assert "❌" in md and "hỏng bắt buộc: 1" in md
    assert kc.main(["--goc", str(tmp_path / "goc"), "--ra", str(tmp_path / "ra"), "--bat-buoc", "bi-mat"]) == 0


def test_cli_cp1252(tmp_path):
    mk_app(tmp_path / "goc", "ok")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(Path(kc.__file__)), "--goc", str(tmp_path / "goc"), "--ra", str(tmp_path / "ra")],
                          capture_output=True, env=env, timeout=60)
    assert b"Traceback" not in proc.stderr and proc.returncode == 0
