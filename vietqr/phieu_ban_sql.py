"""Đọc phiếu bán từ SQL Server HTsoft — CHỈ ĐỌC (SELECT).

Câu SELECT có hình dạng cố định; chỉ tên bảng/cột lấy từ cấu hình và phải
qua kiểm tra định danh. Giá trị lọc luôn đi qua tham số `?`.
Cột chưa kiểm chứng để trống trong cấu hình -> app chạy chế độ nhập tay.
"""
import json
import pathlib
import re
from contextlib import closing

BAT_BUOC = [
    "server", "database", "bang_phieu", "cot_id", "cot_so_phieu", "cot_ngay",
    "cot_khach_id", "cot_tong_tien", "bang_chi_tiet", "cot_ct_phieu_id",
    "cot_ct_mh_id", "cot_mh_ten",
]
_DINH_DANH = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


def doc_cau_hinh(path):
    path = pathlib.Path(path)
    if not path.exists():
        return None, f"Chưa có {path.name} — đang ở chế độ nhập tay"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    thieu = [k for k in BAT_BUOC if not str(cfg.get(k, "")).strip()]
    if thieu:
        return None, "Cấu hình SQL còn trống: " + ", ".join(thieu) + " — đang ở chế độ nhập tay"
    for k in BAT_BUOC[2:]:
        if not _DINH_DANH.fullmatch(cfg[k]):
            return None, f"Tên bảng/cột không hợp lệ ở '{k}'"
    cfg["so_ngay"] = int(cfg.get("so_ngay", 30))
    return cfg, "Đã nối SQL"


def _q(name):
    return f"[{name}]"


def sql_danh_sach(c):
    return (
        f"SELECT TOP 300 h.{_q(c['cot_id'])} AS ID, h.{_q(c['cot_so_phieu'])} AS SOPHIEU, "
        f"h.{_q(c['cot_ngay'])} AS NGAY, k.[KHTEN] AS KHACH, h.{_q(c['cot_tong_tien'])} AS TONG "
        f"FROM dbo.{_q(c['bang_phieu'])} h "
        f"LEFT JOIN dbo.[KHACHHANG] k ON k.[KHID] = h.{_q(c['cot_khach_id'])} "
        f"WHERE h.{_q(c['cot_ngay'])} >= DATEADD(day, -?, GETDATE()) "
        f"AND (? = '' OR h.{_q(c['cot_so_phieu'])} LIKE ? OR k.[KHTEN] LIKE ?) "
        f"ORDER BY h.{_q(c['cot_ngay'])} DESC"
    )


def sql_san_pham(c):
    return (
        f"SELECT m.{_q(c['cot_mh_ten'])} AS TEN "
        f"FROM dbo.{_q(c['bang_chi_tiet'])} ct "
        f"JOIN dbo.[MATHANG] m ON m.[MHID] = ct.{_q(c['cot_ct_mh_id'])} "
        f"WHERE ct.{_q(c['cot_ct_phieu_id'])} = ?"
    )


def chuoi_ket_noi(c, drivers):
    driver = next((d for d in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server")
                   if d in drivers), "SQL Server")
    return (f"DRIVER={{{driver}}};SERVER={c['server']};DATABASE={c['database']};"
            "Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
            "ApplicationIntent=ReadOnly")


class NguonSQL:
    def __init__(self, cfg, connect=None):
        self.cfg = cfg
        self._connect = connect

    def _conn(self):
        if self._connect:
            return self._connect()
        import pyodbc
        return pyodbc.connect(chuoi_ket_noi(self.cfg, pyodbc.drivers()), timeout=10, autocommit=True)

    def danh_sach(self, tu_khoa=""):
        like = f"%{tu_khoa}%"
        with closing(self._conn()) as cn:
            cur = cn.cursor()
            cur.execute(sql_danh_sach(self.cfg), [self.cfg["so_ngay"], tu_khoa, like, like])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def san_pham(self, phieu_id):
        with closing(self._conn()) as cn:
            cur = cn.cursor()
            cur.execute(sql_san_pham(self.cfg), [phieu_id])
            ten = []
            for (t,) in cur.fetchall():
                t = (t or "").strip()
                if t and t not in ten:
                    ten.append(t)
            return ", ".join(ten)
