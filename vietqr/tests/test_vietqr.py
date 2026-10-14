"""Kiểm thử lõi VietQR và phần SQL (không cần SQL Server, không cần mạng).

Đã đối chiếu thủ công 2 mẫu QR do SePay sinh: chuỗi trùng từng ký tự.
Mẫu thật có tên khách nên không đưa vào kho công khai; ở đây dùng tên giả.
"""
import pathlib
import sqlite3
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from phieu_ban_sql import NguonSQL, chuoi_ket_noi, doc_cau_hinh, sql_danh_sach  # noqa: E402
from vietqr_core import GHI_CHU_TOI_DA, crc16, khong_dau, noi_dung_ck, payload, ve_qr  # noqa: E402

ACB = {"code": "ACB", "bank": "ACB", "bin": "970416", "stk": "260919009", "name": "CONG TY TEST"}


def tach_tlv(s):
    out, i = {}, 0
    while i < len(s):
        tag, n = s[i:i + 2], int(s[i + 2:i + 4])
        out[tag] = s[i + 4:i + 4 + n]
        i += 4 + n
    return out


def test_crc_vector_chuan():
    assert crc16("123456789") == "29B1"  # CRC-16/CCITT-FALSE


def test_qr_tinh_khop_mau_da_kiem():
    assert payload("970416", "260919009") == (
        "00020101021138530010A0000007270123000697041601092609190090208QRIBFTTA"
        "53037045802VN6304D919")


def test_qr_co_so_tien_va_noi_dung():
    p = payload("970416", "260919009", 38300000, "NGUYEN VAN A thanh toan")
    f = tach_tlv(p)
    assert f["01"] == "12" and f["54"] == "38300000" and f["53"] == "704"
    assert tach_tlv(f["62"])["08"] == "NGUYEN VAN A thanh toan"
    assert p[-4:] == crc16(p[:-4])


def test_khong_dau():
    assert khong_dau("Nguyễn Văn Đạt – iPhone 18") == "Nguyen Van Dat iPhone 18"


def test_noi_dung_theo_mau_sepay():
    nd = noi_dung_ck("Nguyễn Văn A", "iPhone 18 Pro 256GB", 38300000)
    assert nd == "NGUYEN VAN A thanh toan tien hang iPhone 18 Pro 256GB 38300000"


def test_noi_dung_dai_bi_rut_gon_ten_sp():
    nd = noi_dung_ck("Nguyen Van A", " ".join(["Tu lanh Side by Side 600L"] * 6), 1000)
    assert len(nd) <= GHI_CHU_TOI_DA and nd.endswith("1000")


def test_loi_dau_vao():
    with pytest.raises(ValueError):
        payload("97041", "260919009")
    with pytest.raises(ValueError):
        payload("970416", "26 09")


def test_ve_qr_tao_anh():
    anh = ve_qr(ACB, 1000, "x" * 200)
    assert anh.width > 300 and anh.height > anh.width


def test_quet_lai_anh_neu_co_opencv():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    anh = ve_qr(ACB, 38300000, "NGUYEN VAN A thanh toan")
    doc = cv2.QRCodeDetector().detectAndDecode(np.array(anh)[:, :, ::-1])[0]
    assert doc == payload("970416", "260919009", 38300000, "NGUYEN VAN A thanh toan")


# ---------- SQL ----------
CFG = {"server": "s", "database": "d", "bang_phieu": "BANHOADON", "cot_id": "BHDID",
       "cot_so_phieu": "BHDCODE", "cot_ngay": "NGAYHD", "cot_khach_id": "KHID",
       "cot_tong_tien": "TONG", "bang_chi_tiet": "BANCTHOADON", "cot_ct_phieu_id": "BHDID",
       "cot_ct_mh_id": "MHID", "cot_mh_ten": "TEN"}


def test_cau_hinh_thieu_thi_nhap_tay(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"server": "s", "cot_tong_tien": ""}', encoding="utf-8")
    cfg, msg = doc_cau_hinh(f)
    assert cfg is None and "nhập tay" in msg
    assert doc_cau_hinh(tmp_path / "khong-co.json")[0] is None


def test_cau_hinh_chan_ten_cot_doc_hai(tmp_path):
    import json
    f = tmp_path / "c.json"
    f.write_text(json.dumps(dict(CFG, cot_tong_tien="TONG]; DROP TABLE X--")), encoding="utf-8")
    cfg, msg = doc_cau_hinh(f)
    assert cfg is None and "không hợp lệ" in msg


def test_sql_chi_doc_va_dung_tham_so():
    s = sql_danh_sach(dict(CFG, so_ngay=30))
    assert s.startswith("SELECT ") and s.count("?") == 4
    for cam in ("UPDATE", "INSERT", "DELETE", "DROP", "EXEC", ";"):
        assert cam not in s.upper()


def test_chuoi_ket_noi_uu_tien_driver_18():
    c = chuoi_ket_noi(CFG, ["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"])
    assert "ODBC Driver 18" in c and "Encrypt=no" in c and "Trusted_Connection=yes" in c


def test_nguon_sql_doc_phieu_va_san_pham():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript("""
        ATTACH ':memory:' AS dbo;
        CREATE TABLE dbo.BANHOADON (BHDID INT, BHDCODE TEXT, NGAYHD TEXT, KHID INT, TONG INT);
        CREATE TABLE dbo.KHACHHANG (KHID INT, KHTEN TEXT);
        CREATE TABLE dbo.BANCTHOADON (BHDID INT, MHID INT);
        CREATE TABLE dbo.MATHANG (MHID INT, TEN TEXT);
        INSERT INTO dbo.BANHOADON VALUES (1, 'PB001', date('now'), 7, 38300000);
        INSERT INTO dbo.KHACHHANG VALUES (7, 'Nguyen Van A');
        INSERT INTO dbo.BANCTHOADON VALUES (1, 9), (1, 9), (1, 10);
        INSERT INTO dbo.MATHANG VALUES (9, 'iPhone 18 Pro'), (10, 'Op lung');
    """)

    class Con:  # bọc cursor sqlite, dịch cú pháp T-SQL tối thiểu
        def __init__(self):
            self.c = db.cursor()

        def execute(self, sql, params):
            sql = sql.replace("SELECT TOP 300", "SELECT").replace(
                "DATEADD(day, -?, GETDATE())", "date('now', '-' || ? || ' day')")
            self.c.execute(sql, params)

        def __getattr__(self, k):
            return getattr(self.c, k)

    class Ket:
        def cursor(self):
            return Con()

        def close(self):
            pass

    n = NguonSQL(dict(CFG, so_ngay=30), connect=Ket)
    rows = n.danh_sach("PB0")
    assert rows == [{"ID": 1, "SOPHIEU": "PB001", "NGAY": rows[0]["NGAY"], "KHACH": "Nguyen Van A",
                     "TONG": 38300000}]
    assert n.danh_sach("khong-co") == []
    assert n.san_pham(1) == "iPhone 18 Pro, Op lung"
