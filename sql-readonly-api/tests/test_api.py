import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as api  # noqa: E402

TOKEN = "t" * 48
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class SqliteBackend:
    dialect = "sqlite"

    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.execute("CREATE TABLE vw_API_TonGiaBan (ParentSKU TEXT, Ten TEXT, TonBanSan INT, GiaLe INT)")
        rows = [(f"SKU{i:03d}", f"San pham {i}", i, 1000 * i) for i in range(1, 121)]
        self.conn.executemany("INSERT INTO vw_API_TonGiaBan VALUES (?,?,?,?)", rows)
        self.calls: list[tuple[str, list]] = []

    def query(self, sql, params):
        self.calls.append((sql, params))
        cur = self.conn.execute(sql, params)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def make_views(**override):
    spec = {
        "source": "vw_API_TonGiaBan",
        "columns": ["ParentSKU", "Ten", "TonBanSan", "GiaLe"],
        "filter_columns": ["ParentSKU"],
        "order_by": "ParentSKU",
        "max_rows": 100,
        "description": "thu",
    }
    spec.update(override)
    return api.parse_views({"views": {"ton-gia-ban": spec}})


@pytest.fixture
def backend():
    return SqliteBackend()


@pytest.fixture
def client(backend):
    app = api.create_app(token=TOKEN, views=make_views(), backend=backend)
    return TestClient(app)


def test_health_khong_can_token_va_khong_lo_du_lieu(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_khong_co_docs(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer sai"}, {"Authorization": f"Basic {TOKEN}"}])
def test_thieu_hoac_sai_token_bi_401(client, headers):
    assert client.get("/v1/views", headers=headers).status_code == 401
    assert client.get("/v1/views/ton-gia-ban", headers=headers).status_code == 401


def test_liet_ke_view(client):
    r = client.get("/v1/views", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["views"][0]["name"] == "ton-gia-ban"


def test_trang_mac_dinh_nho_va_has_more(client):
    body = client.get("/v1/views/ton-gia-ban", headers=AUTH).json()
    assert body["limit"] == api.DEFAULT_LIMIT == body["count"]
    assert body["has_more"] is True
    assert body["rows"][0]["ParentSKU"] == "SKU001"


def test_limit_bi_chan_o_max_rows_va_phan_trang(client):
    body = client.get("/v1/views/ton-gia-ban?limit=100000&offset=100", headers=AUTH).json()
    assert body["limit"] == 100
    assert body["count"] == 20 and body["has_more"] is False


def test_loc_bang_cot_cho_phep(client):
    body = client.get("/v1/views/ton-gia-ban?ParentSKU=SKU007", headers=AUTH).json()
    assert body["count"] == 1 and body["rows"][0]["Ten"] == "San pham 7"


def test_loc_cot_khong_cho_phep_bi_400(client):
    r = client.get("/v1/views/ton-gia-ban?GiaLe=1000", headers=AUTH)
    assert r.status_code == 400


def test_sql_injection_qua_gia_tri_loc_khong_co_tac_dung(client, backend):
    r = client.get("/v1/views/ton-gia-ban", params={"ParentSKU": "' OR 1=1 --"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["count"] == 0
    sql, params = backend.calls[-1]
    assert "OR 1=1" not in sql and "' OR 1=1 --" in params


def test_sql_injection_qua_ten_cot_loc_bi_chan(client):
    r = client.get("/v1/views/ton-gia-ban", params={"ParentSKU];DROP TABLE x;--": "a"}, headers=AUTH)
    assert r.status_code == 400


def test_limit_offset_khong_phai_so_bi_400(client):
    assert client.get("/v1/views/ton-gia-ban?limit=abc", headers=AUTH).status_code == 400
    assert client.get("/v1/views/ton-gia-ban?offset=-1", headers=AUTH).status_code == 400


def test_view_khong_ton_tai_404(client):
    assert client.get("/v1/views/khong-co", headers=AUTH).status_code == 404


def test_loi_db_khong_lo_chi_tiet(backend):
    def boom(sql, params):
        raise RuntimeError("Login failed for user sa password=abc")

    backend.query = boom
    c = TestClient(api.create_app(token=TOKEN, views=make_views(), backend=backend))
    r = c.get("/v1/views/ton-gia-ban", headers=AUTH)
    assert r.status_code == 502 and "password" not in r.text


def test_sai_token_nhieu_lan_bi_khoa_tam(client):
    for _ in range(10):
        assert client.get("/v1/views", headers={"Authorization": "Bearer sai"}).status_code == 401
    assert client.get("/v1/views", headers={"Authorization": "Bearer sai"}).status_code == 429
    assert client.get("/v1/views", headers=AUTH).status_code == 429  # IP đang bị khóa


def test_gioi_han_so_luot_moi_phut(backend):
    c = TestClient(api.create_app(token=TOKEN, views=make_views(), backend=backend, requests_per_minute=3))
    codes = [c.get("/v1/views", headers=AUTH).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_audit_log_khong_chua_du_lieu_va_token(tmp_path, backend):
    log = tmp_path / "audit.log"
    c = TestClient(api.create_app(token=TOKEN, views=make_views(), backend=backend, audit_path=log))
    c.get("/v1/views/ton-gia-ban", params={"ParentSKU": "SKU005"}, headers=AUTH)
    text = log.read_text(encoding="utf-8")
    assert "ton-gia-ban" in text and "ParentSKU" in text
    assert TOKEN not in text and "SKU005" not in text and "San pham" not in text


# ---------- kiểm tra cấu hình


def test_token_ngan_bi_tu_choi(backend):
    with pytest.raises(api.ConfigError):
        api.create_app(token="ngan", views=make_views(), backend=backend)


@pytest.mark.parametrize("cot", ["GiaVon", "gia_nhap", "NCC_ReNhat", "SoDienThoai", "MatKhau", "ApiKey", "CostPrice"])
def test_cot_nhay_cam_bi_chan(cot):
    with pytest.raises(api.ConfigError):
        make_views(columns=["ParentSKU", cot], filter_columns=[])


def test_chi_cho_mo_view_vw_API_khong_mo_bang_goc():
    with pytest.raises(api.ConfigError):
        make_views(source="dbo.MATHANG")
    make_views(source="dbo.vw_API_TonGiaBan")


@pytest.mark.parametrize("bad", ["x];DROP TABLE a;--", "a b", "1abc", ""])
def test_dinh_danh_xau_bi_tu_choi(bad):
    with pytest.raises(api.ConfigError):
        make_views(columns=["ParentSKU", bad], filter_columns=[])


def test_filter_va_order_phai_nam_trong_columns():
    with pytest.raises(api.ConfigError):
        make_views(filter_columns=["KhongCo"])
    with pytest.raises(api.ConfigError):
        make_views(order_by="KhongCo")


def test_max_rows_khong_vuot_5000():
    with pytest.raises(api.ConfigError):
        make_views(max_rows=10**6)


def test_views_example_json_hop_le():
    api.load_views(Path(__file__).resolve().parent.parent / "views.example.json")


def test_cau_select_sql_server_dung_offset_fetch():
    spec = make_views()["ton-gia-ban"]
    sql, params = api.build_select(spec, "sqlserver", {"ParentSKU": "A"}, 50, 100)
    assert sql == (
        "SELECT [ParentSKU], [Ten], [TonBanSan], [GiaLe] FROM [vw_API_TonGiaBan] "
        "WHERE [ParentSKU] = ? ORDER BY [ParentSKU] OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    )
    assert params == ["A", 100, 51]


def test_pick_driver_uu_tien_18_roi_17():
    assert api.pick_driver(["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"]).endswith("18 for SQL Server")
    assert api.pick_driver(["ODBC Driver 17 for SQL Server"]).endswith("17 for SQL Server")
    with pytest.raises(RuntimeError):
        api.pick_driver(["SQLite"])


@pytest.mark.parametrize("flags,ok", [({"sysadmin": 0, "db_owner": 0, "db_datawriter": 0, "db_ddladmin": 0}, True),
                                      ({"sysadmin": 1, "db_owner": 0, "db_datawriter": 0, "db_ddladmin": 0}, False),
                                      ({"sysadmin": 0, "db_owner": 1, "db_datawriter": 0, "db_ddladmin": 0}, False),
                                      ({"sysadmin": 0, "db_owner": 0, "db_datawriter": 1, "db_ddladmin": 0}, False)])
def test_tu_choi_chay_khi_tai_khoan_co_quyen_ghi(flags, ok):
    class Fake:
        def query(self, sql, params):
            return [flags]

    if ok:
        api.ensure_least_privilege(Fake())
    else:
        with pytest.raises(RuntimeError):
            api.ensure_least_privilege(Fake())


def test_odbc_value_thoat_dau_ngoac():
    assert api._odbc_value("p;w}d") == "{p;w}}d}"


def test_load_env_file_khong_ghi_de(tmp_path, monkeypatch):
    f = tmp_path / "config.env"
    f.write_text('# ghi chu\nDMV_A=1\nDMV_B="hai"\n', encoding="utf-8")
    monkeypatch.setenv("DMV_A", "giu")
    monkeypatch.delenv("DMV_B", raising=False)
    api.load_env_file(f)
    import os
    assert os.environ["DMV_A"] == "giu" and os.environ["DMV_B"] == "hai"
    monkeypatch.delenv("DMV_B", raising=False)
