import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as qr
import tao_tem

TOKEN = "t" * 40


@pytest.fixture
def moi_truong(tmp_path: Path):
    tep_gia = tmp_path / "gia-live.json"
    tep_gia.write_text(json.dumps({"san_pham": [
        {"sku": "TABA11W464", "ten": "Samsung Galaxy Tab A11 WiFi 4/64", "gia": 3790000,
         "ton": {"30LL": 14, "VV": 0}, "thong_so": ["Màn 8.7 inch", "Pin 5.100mAh"]},
        {"sku": "N105PRO", "ten": "Nokia 105 4G Pro", "gia": 689000, "ton": {"30LL": 0, "BT": 3}},
    ]}), encoding="utf-8")
    ch = qr.CauHinh(tep_gia_live=tep_gia, thu_muc_du_lieu=tmp_path / "du-lieu",
                    thu_muc_rieng_tu=tmp_path / "rieng-tu", thu_muc_chuong=tmp_path / "chuong",
                    token_bao_cao=TOKEN, gioi_han_moi_phut=1000)
    return ch, TestClient(qr.create_app(ch))


def test_trang_sp_gia_tuoi(moi_truong):
    _, c = moi_truong
    r = c.get("/sp/TABA11W464?cn=30LL").json()
    assert r["gia"] == 3790000 and r["gia_trang_thai"] == "live" and r["con_hang_tai_day"]


def test_con_hang_noi_khac(moi_truong):
    _, c = moi_truong
    r = c.get("/sp/N105PRO?cn=30LL").json()
    assert not r["con_hang_tai_day"] and r["con_hang_noi_khac"] == ["Ba Tri"]


def test_gia_cu_thi_an_gia(moi_truong):
    ch, c = moi_truong
    cu = time.time() - 3600
    os.utime(ch.tep_gia_live, (cu, cu))
    r = c.get("/sp/TABA11W464?cn=30LL").json()
    assert r["gia"] is None and r["gia_trang_thai"] == "lien_he"


def test_tep_co_gia_von_bi_tu_choi(moi_truong):
    ch, c = moi_truong
    ch.tep_gia_live.write_text(json.dumps([{"sku": "X1", "ten": "x", "gia": 1, "gia_von": 1}]), encoding="utf-8")
    assert c.get("/sp/X1").status_code == 404  # không đọc được = không trả gì


def test_goi_tu_van_bao_chuong(moi_truong):
    ch, c = moi_truong
    assert c.post("/su-kien", json={"loai": "goi_tu_van", "sku": "TABA11W464", "cn": "30LL", "ke": "A3", "nguon": "tem"}).status_code == 200
    tin = [json.loads(p.read_text(encoding="utf-8")) for p in ch.thu_muc_chuong.glob("qr-tu-van-*.json")]
    assert len(tin) == 1 and "kệ A3" in tin[0]["noi_dung"] and tin[0]["chi_nhanh"] == "30 Lê Lợi"


def test_dang_ky_can_dong_y_va_khong_lo_sdt(moi_truong):
    ch, c = moi_truong
    assert c.post("/dang-ky", json={"sdt": "0901234567", "dong_y": False}).status_code == 400
    assert c.post("/dang-ky", json={"sdt": "12345", "dong_y": True}).status_code == 400
    assert c.post("/dang-ky", json={"sdt": "0901234567", "dong_y": True, "imei": "356789012345678", "nguon": "bh", "cn": "30LL"}).status_code == 200
    assert c.post("/huy-dang-ky", json={"sdt": "0901234567"}).status_code == 200
    rieng = (ch.thu_muc_rieng_tu / "khach-dong-y.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(d)["hanh_dong"] for d in rieng] == ["dong_y", "rut_dong_y"]
    assert "0901234567" not in (ch.thu_muc_du_lieu / "su-kien.jsonl").read_text(encoding="utf-8")


def test_bao_cao_theo_nguon(moi_truong):
    _, c = moi_truong
    for nguon in ("tem", "tem", "poster"):
        c.post("/su-kien", json={"loai": "quet", "sku": "TABA11W464", "cn": "30LL", "nguon": nguon})
    assert c.get("/bao-cao").status_code == 401
    r = c.get("/bao-cao", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert r["nguon"] == {"tem": 2, "poster": 1} and r["nguon_loai"]["tem:quet"] == 2


def test_tham_so_xau_bi_chan(moi_truong):
    _, c = moi_truong
    assert c.post("/su-kien", json={"loai": "quet", "sku": "a b", "cn": "30LL"}).status_code == 400
    assert c.post("/su-kien", json={"loai": "quet", "sku": "X", "cn": "HN"}).status_code == 400
    assert c.post("/su-kien", json={"loai": "xoa", "sku": "X", "cn": "30LL"}).status_code == 400


def test_khong_cho_rieng_tu_trong_drive(monkeypatch):
    for k, v in {"QR_TOKEN_BAO_CAO": TOKEN, "QR_TEP_GIA_LIVE": "a", "QR_THU_MUC_DU_LIEU": "b",
                 "QR_THU_MUC_CHUONG": "c", "QR_THU_MUC_RIENG_TU": r"G:\My Drive\DMV-Cloud-Bridge\x"}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(qr.CauHinhLoi):
        qr.cau_hinh_tu_env()


def test_in_tem(tmp_path):
    csv_p = tmp_path / "ds.csv"
    csv_p.write_text("sku,ten,cn,ke,nguon\nTABA11W464,Samsung Galaxy Tab A11 WiFi 4/64,30LL,A3,tem\nN105PRO,Nokia 105 4G Pro,BT,,poster\n", encoding="utf-8")
    ra = tmp_path / "tem.pdf"
    assert tao_tem.in_pdf(tao_tem.doc_danh_sach(str(csv_p)), "https://qr.example.vn", str(ra)) == 2
    assert ra.read_bytes()[:4] == b"%PDF"
    assert tao_tem.tao_link("https://qr.example.vn/", "N105PRO", "BT", "", "poster") == "https://qr.example.vn/?sku=N105PRO&cn=BT&nguon=poster"


def test_danh_sach_sai_khong_in(tmp_path):
    csv_p = tmp_path / "ds.csv"
    csv_p.write_text("sku,ten,cn,ke,nguon\nX1,abc,HANOI,,tem\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        tao_tem.doc_danh_sach(str(csv_p))
