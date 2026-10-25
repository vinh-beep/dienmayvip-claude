import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app as api  # noqa: E402
import kiem_ket_noi as kk  # noqa: E402
from test_api import SqliteBackend, make_views  # noqa: E402

GOOD_ENV = {
    "DMV_API_TOKEN": "t" * 40, "DMV_SQL_SERVER": "s", "DMV_SQL_DATABASE": "d",
    "DMV_SQL_USER": "u", "DMV_SQL_PASSWORD": "p",
}


def write_views(tmp_path, spec=None):
    spec = spec or {
        "source": "vw_API_TonGiaBan", "columns": ["ParentSKU", "Ten", "TonBanSan", "GiaLe"],
        "filter_columns": ["ParentSKU"], "order_by": "ParentSKU",
    }
    p = tmp_path / "views.json"
    p.write_text(json.dumps({"views": {"ton-gia-ban": spec}}), encoding="utf-8")
    return p


def test_kiem_nhe_dat(tmp_path):
    res, views = kk.kiem_nhe(GOOD_ENV, write_views(tmp_path))
    assert all(ok for ok, _ in res) and "ton-gia-ban" in views


def test_kiem_nhe_bat_thieu_cau_hinh_va_token_ngan(tmp_path):
    env = dict(GOOD_ENV, DMV_API_TOKEN="ngan")
    del env["DMV_SQL_PASSWORD"]
    res, _ = kk.kiem_nhe(env, write_views(tmp_path))
    bad = [m for ok, m in res if not ok]
    assert any("DMV_API_TOKEN" in m for m in bad) and any("DMV_SQL_PASSWORD" in m for m in bad)


def test_kiem_nhe_bat_views_json_nguy_hiem(tmp_path):
    p = write_views(tmp_path, {"source": "dbo.MATHANG", "columns": ["GiaVon"], "order_by": "GiaVon"})
    res, views = kk.kiem_nhe(GOOD_ENV, p)
    assert views == {} and any(not ok and "views.json lỗi" in m for ok, m in res)


def test_kiem_nhe_khong_cham_vao_sql(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "SqlServerBackend", lambda *a, **k: (_ for _ in ()).throw(AssertionError("không được nối SQL")))
    kk.kiem_nhe(GOOD_ENV, write_views(tmp_path))


class Priv(SqliteBackend):
    def __init__(self, flags):
        super().__init__()
        self.flags = flags

    def query(self, sql, params):
        if "IS_SRVROLEMEMBER" in sql:
            return [self.flags]
        return super().query(sql, params)


SAFE = {"sysadmin": 0, "db_owner": 0, "db_datawriter": 0, "db_ddladmin": 0}


def test_kiem_day_du_dat():
    res = kk.kiem_day_du(make_views(), Priv(SAFE))
    assert all(ok for ok, _ in res), res
    assert any("đọc được 1 dòng thật, đủ 4 cột" in m for _, m in res)


def test_kiem_day_du_bat_quyen_ghi():
    res = kk.kiem_day_du(make_views(), Priv(dict(SAFE, db_owner=1)))
    assert not res[0][0] and "db_owner" in res[0][1]


def test_kiem_day_du_bat_cot_khai_bao_ma_view_khong_co():
    spec = api.ViewSpec("ton-gia-ban", "vw_API_TonGiaBan", ("ParentSKU", "CotKhongCo"), (), "ParentSKU", 10, "")
    res = kk.kiem_day_du({"ton-gia-ban": spec}, Priv(SAFE))
    assert any(not ok and "đọc thử lỗi" in m for ok, m in res)


def test_kiem_day_du_bat_loi_doc_view():
    class Hong(Priv):
        def query(self, sql, params):
            if "vw_API" in sql:
                raise RuntimeError("password=abc")
            return super().query(sql, params)

    res = kk.kiem_day_du(make_views(), Hong(SAFE))
    assert any(not ok and "đọc thử lỗi" in m for ok, m in res)
    assert not any("password" in m for _, m in res)  # không in chi tiết lỗi


def test_view_rong_van_dat_nhung_ghi_chu():
    b = Priv(SAFE)
    b.conn.execute("DELETE FROM vw_API_TonGiaBan")
    res = kk.kiem_day_du(make_views(), b)
    assert all(ok for ok, _ in res) and any("đang rỗng" in m for _, m in res)


def test_cli_khong_sap_khi_console_la_cp1252(tmp_path):
    import os
    import subprocess
    env = {k: v for k, v in os.environ.items() if not k.startswith("DMV_")}
    env.update(PYTHONIOENCODING="cp1252", DMV_VIEWS_FILE=str(tmp_path / "khong-co.json"))
    proc = subprocess.run([sys.executable, str(Path(kk.__file__)), "--nhe"], capture_output=True, env=env, timeout=60)
    assert b"Traceback" not in proc.stderr, proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 1 and "HỎNG".encode("utf-8") in proc.stdout
