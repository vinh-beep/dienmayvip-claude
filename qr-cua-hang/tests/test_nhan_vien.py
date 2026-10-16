import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as qr
import nhan_vien as nv

MA = "nv-30ll-abc123"


@pytest.fixture
def moi_truong(tmp_path: Path):
    tep = tmp_path / "gia.json"
    tep.write_text(json.dumps({"san_pham": [
        {"sku": "DT-SS-08", "ten": "SAMSUNG A36 5G 8G 128G", "gia": 7540000, "ton": {"30LL": 1, "BT": 6}},
        {"sku": "DT-NK-02", "ten": "NOKIA 105 4G PRO", "gia": 689000, "ton": {"30LL": 724}},
        {"sku": "MTB-MI-03", "ten": "REDMI PAD 2 WIFI", "gia": 6190000, "ton": {"30LL": 0, "TP": 1}},
        {"sku": "DT-AP-01", "ten": "IPHONE 17 PRO MAX 1TB", "gia": 46980000, "ton": {"30LL": 5}},
    ]}), encoding="utf-8")
    ch = qr.CauHinh(tep_gia_live=tep, thu_muc_du_lieu=tmp_path / "dl", thu_muc_rieng_tu=tmp_path / "rt",
                    thu_muc_chuong=tmp_path / "chuong", token_bao_cao="t" * 40, gioi_han_moi_phut=1000,
                    ma_nhan_vien=(MA,), thu_muc_yeu_cau=tmp_path / "yeu-cau")
    return ch, TestClient(qr.create_app(ch))


H = {"X-Ma-NV": MA}


def test_phan_loai_nguong():
    assert [nv.phan_loai(x, 2, 30) for x in (0, 1, 2, 3, 29, 30)] == ["HET", "SAP_HET", "SAP_HET", "DU", "DU", "TON_LON"]


def test_can_ma_nhan_vien(moi_truong):
    _, c = moi_truong
    assert c.get("/nv/sp/DT-SS-08?cn=30LL").status_code == 401
    assert c.get("/nv/sp/DT-SS-08?cn=30LL", headers={"X-Ma-NV": "sai-ma-123"}).status_code == 401


def test_goi_y_chuyen_kho(moi_truong):
    _, c = moi_truong
    d = c.get("/nv/sp/DT-SS-08?cn=30LL", headers=H).json()
    o_day = next(k for k in d["kho"] if k["cn"] == "30LL")
    assert o_day["loai"] == "SAP_HET"
    assert d["de_xuat"][0] == {"loai": "chuyen_kho", "cn_di": "BT", "cn_den": "30LL", "so_luong": 2,
                               "ly_do": "30 Lê Lợi còn 1, Ba Tri còn 6"}
    assert all(g["loai"] != "dat_ncc" for g in d["de_xuat"])  # hệ thống còn 7, chưa cần đặt


def test_goi_y_dat_ncc_khi_ca_he_thong_thap(moi_truong):
    _, c = moi_truong
    d = c.get("/nv/sp/MTB-MI-03?cn=30LL", headers=H).json()
    assert [g["loai"] for g in d["de_xuat"]] == ["dat_ncc"]  # TP chỉ còn 1, không rút được


def test_khong_lo_gia(moi_truong):
    _, c = moi_truong
    raw = c.get("/nv/sp/DT-SS-08?cn=30LL", headers=H).text
    assert "7540000" not in raw and "gia" not in json.loads(raw)


def test_bang_phan_loai(moi_truong):
    _, c = moi_truong
    d = c.get("/nv/phan-loai?cn=30LL", headers=H).json()
    ten = {k: [r["sku"] for r in v] for k, v in d["nhom"].items()}
    assert ten == {"HET": ["MTB-MI-03"], "SAP_HET": ["DT-SS-08"], "DU": ["DT-AP-01"], "TON_LON": ["DT-NK-02"]}


def test_de_nghi_chuyen_kho_va_dat_ncc(moi_truong):
    ch, c = moi_truong
    assert c.post("/nv/yeu-cau", headers=H, json={"loai": "chuyen_kho", "sku": "DT-SS-08", "cn_den": "30LL", "cn_di": "BT", "so_luong": 2}).status_code == 200
    assert c.post("/nv/yeu-cau", headers=H, json={"loai": "dat_ncc", "sku": "MTB-MI-03", "cn_den": "30LL", "so_luong": 3}).status_code == 200
    tep = sorted(p.name.split("-")[3] for p in ch.thu_muc_yeu_cau.glob("qr-de-nghi-*.json"))
    assert len(tep) == 2
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in ch.thu_muc_yeu_cau.glob("qr-de-nghi-*.json")]
    assert all(r["trang_thai"] == "cho_duyet" for r in recs)
    assert MA not in json.dumps(recs)  # không lưu nguyên mã nhân viên


def test_de_nghi_sai_bi_chan(moi_truong):
    _, c = moi_truong
    def gui(**kw):
        body = {"loai": "chuyen_kho", "sku": "DT-SS-08", "cn_den": "30LL", "cn_di": "BT", "so_luong": 2} | kw
        return c.post("/nv/yeu-cau", headers=H, json=body).status_code
    assert gui(so_luong=7) == 400          # Ba Tri chỉ còn 6
    assert gui(cn_di="30LL") == 400        # chuyển về chính nó
    assert gui(so_luong=0) == 400
    assert gui(loai="xoa_kho") == 400
    assert c.post("/nv/yeu-cau", json={"loai": "dat_ncc", "sku": "DT-SS-08", "cn_den": "30LL", "so_luong": 1}).status_code == 401


def test_tat_khi_khong_cau_hinh(tmp_path):
    ch = qr.CauHinh(tep_gia_live=tmp_path / "x.json", thu_muc_du_lieu=tmp_path, thu_muc_rieng_tu=tmp_path / "rt",
                    thu_muc_chuong=tmp_path, token_bao_cao="t" * 40)
    assert TestClient(qr.create_app(ch)).get("/nv/phan-loai").status_code == 404


def test_ma_ngan_bi_tu_choi(monkeypatch):
    for k, v in {"QR_TOKEN_BAO_CAO": "t" * 40, "QR_TEP_GIA_LIVE": "a", "QR_THU_MUC_DU_LIEU": "b",
                 "QR_THU_MUC_CHUONG": "c", "QR_THU_MUC_RIENG_TU": "/data/rt", "QR_MA_NHAN_VIEN": "ngan",
                 "QR_THU_MUC_YEU_CAU": "/data/yc"}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(qr.CauHinhLoi):
        qr.cau_hinh_tu_env()
