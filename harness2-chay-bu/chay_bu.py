"""Chạy bù việc bị lỡ cho Harness² (anh Vĩnh duyệt 25/10/2026: chạy bù, TRỪ ngân hàng/tiền).

Gọi MỘT LẦN khi Harness² khởi động (sau khi máy bật lại). Không tự đặt lịch, không tạo scheduled task.
Mặc định CHẠY THỬ: chỉ in kế hoạch. Chỉ chạy lệnh thật khi có cờ --chay-that.
  python chay_bu.py --config chay_bu.config.json                 # in kế hoạch
  python chay_bu.py --config chay_bu.config.json --chay-that     # chạy bù thật

Luật (tinh hoa Cloud 25/10, mục H1-H10):
  H1  mỗi việc ghi trạng thái bat-dau / xong / loi ra tệp ket-qua-PC-H2-* trong thư mục Bridge.
  H2  việc có giờ lịch đã qua trong cửa sổ (mặc định 12 giờ) mà chưa có 'xong' sau giờ đó -> chạy bù.
      Việc tiền/ngân hàng -> CHỈ BÁO, không chạy. Quá cửa sổ -> báo, không chạy.
  H3  cửa RAM: RAM trống < cần + dự phòng -> hoãn, không ép chạy.
  H5  kiểm quyền trước (Gmail/Drive/SQL...): hỏng quyền -> gom 1 báo cáo, bỏ các việc phụ thuộc.
  H10 chạy TUẦN TỰ, mỗi lúc một tiến trình, không mở cửa sổ console (máy chính từng treo vì cạn heap desktop).
Không gọi AI -> 0 token. Mã thoát: 0 ổn · 1 có việc lỗi · 2 có việc chờ anh (tiền/quá cửa sổ/hỏng quyền/hoãn RAM).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

VN = timezone(timedelta(hours=7))
TEP_TRANG_THAI = "trang-thai-h2.json"
# Tên/nhóm dính tiền -> không bao giờ tự chạy bù.
RE_TIEN = re.compile(r"BANK|NGAN[ _-]?HANG|NGÂN[ _-]?HÀNG|SO[ _-]?PHU|SỔ[ _-]?PHỤ|THANH[ _-]?TOAN|THANH[ _-]?TOÁN|CHUYEN[ _-]?KHOAN|TAI[ _-]?CHINH|TÀI[ _-]?CHÍNH", re.I)


def la_viec_tien(viec: dict) -> bool:
    return viec.get("nhom") == "tien" or bool(RE_TIEN.search(viec.get("ten", "")))


def gio_lich_gan_nhat(lich: list[str], bay_gio: datetime) -> datetime | None:
    """Giờ lịch (HH:MM, hằng ngày, giờ VN) gần nhất <= bay_gio, xét hôm nay và hôm qua."""
    ung_vien = []
    for hhmm in lich:
        h, m = (int(x) for x in hhmm.split(":"))
        for lui in (0, 1):
            ngay = (bay_gio - timedelta(days=lui)).date()
            t = datetime(ngay.year, ngay.month, ngay.day, h, m, tzinfo=VN)
            if t <= bay_gio:
                ung_vien.append(t)
    return max(ung_vien, default=None)


def lap_ke_hoach(ds_viec: list[dict], trang_thai: dict, bay_gio: datetime, cua_so_gio: float = 12) -> dict:
    """Chia việc: chay_bu / chi_bao_tien / qua_cua_so / da_xong. Không chạy gì."""
    kh = {"chay_bu": [], "chi_bao_tien": [], "qua_cua_so": [], "da_xong": []}
    for v in ds_viec:
        if not v.get("bat", True):
            continue
        hen = gio_lich_gan_nhat(v.get("lich", []), bay_gio)
        if hen is None:
            continue
        xong = trang_thai.get(v["ten"], {}).get("xong")
        if xong and datetime.fromisoformat(xong) >= hen:
            kh["da_xong"].append(v["ten"]); continue
        muc = dict(v, hen=hen.isoformat(timespec="minutes"))
        if la_viec_tien(v):
            kh["chi_bao_tien"].append(muc)
        elif bay_gio - hen > timedelta(hours=v.get("cua_so_gio", cua_so_gio)):
            kh["qua_cua_so"].append(muc)
        else:
            kh["chay_bu"].append(muc)
    return kh


def du_ram(ram_trong_mb: float, can_mb: float, du_phong_mb: float = 1024) -> bool:
    return ram_trong_mb >= can_mb + du_phong_mb


def ram_trong_mb() -> float:
    """RAM trống thật trên Windows (GlobalMemoryStatusEx); máy khác trả vô cực (không chặn)."""
    if sys.platform != "win32":
        return float("inf")
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    ms = MS(); ms.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    return ms.ullAvailPhys / 1024 / 1024


def ten_tep_ket_qua(ten: str, luc: datetime) -> str:
    an_toan = re.sub(r"[^A-Za-z0-9-]+", "-", ten).strip("-")
    return f"ket-qua-PC-H2-{an_toan}-{luc.strftime('%d %m %Y %Hh%Mp')}.md"


def ghi_ket_qua(thu_muc: Path | None, ten: str, buoc: str, luc: datetime, ghi_chu: str = "", ma: int | None = None) -> Path | None:
    """H1: tệp nhỏ lên Bridge. Không ghi nội dung đầu ra của việc (tránh lộ giá/PII)."""
    if thu_muc is None:
        return None
    thu_muc.mkdir(parents=True, exist_ok=True)
    p = thu_muc / ten_tep_ket_qua(ten, luc)
    dong = [f"# Harness² · {ten} · {buoc}", f"- Lúc: {luc.isoformat(timespec='seconds')}"]
    if ma is not None:
        dong.append(f"- Mã thoát: {ma}")
    if ghi_chu:
        dong.append(f"- Ghi chú: {ghi_chu}")
    p.write_text("\n".join(dong) + "\n", encoding="utf-8")
    return p


def chay_lenh(lenh: list[str], gioi_han_giay: int) -> int:
    """H10: một tiến trình, không mở cửa sổ console."""
    co = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        return subprocess.run(lenh, timeout=gioi_han_giay, creationflags=co,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 127


def thuc_hien(kh: dict, trang_thai: dict, kiem_quyen: dict[str, Callable[[], bool]], *, chay_that: bool,
              bay_gio: Callable[[], datetime], doc_ram: Callable[[], float] = ram_trong_mb,
              chay: Callable[[list[str], int], int] = chay_lenh, thu_muc_bridge: Path | None = None) -> dict:
    """Chạy tuần tự danh sách chay_bu. Trả về tóm tắt; cập nhật trang_thai tại chỗ."""
    tom = {"xong": [], "loi": [], "hoan_ram": [], "hong_quyen": {}, "chay_thu": []}
    quyen_ok: dict[str, bool] = {}
    for v in kh["chay_bu"]:
        thieu = []
        for q in v.get("can_quyen", []):
            if q not in quyen_ok:
                f = kiem_quyen.get(q)
                try:
                    quyen_ok[q] = bool(f()) if f else False
                except Exception:
                    quyen_ok[q] = False
            if not quyen_ok[q]:
                thieu.append(q)
        if thieu:
            for q in thieu:
                tom["hong_quyen"].setdefault(q, []).append(v["ten"])
            continue
        if not du_ram(doc_ram(), v.get("can_ram_mb", 0)):
            tom["hoan_ram"].append(v["ten"]); continue
        if not chay_that:
            tom["chay_thu"].append(v["ten"]); continue
        ghi_ket_qua(thu_muc_bridge, v["ten"], "bat-dau", bay_gio(), f"chạy bù lịch {v['hen']}")
        ma = chay(v["lenh"], v.get("gioi_han_giay", 1800))
        luc = bay_gio()
        if ma == 0:
            trang_thai.setdefault(v["ten"], {})["xong"] = luc.isoformat(timespec="seconds")
            tom["xong"].append(v["ten"])
            ghi_ket_qua(thu_muc_bridge, v["ten"], "xong", luc, f"chạy bù lịch {v['hen']}", 0)
        else:
            trang_thai.setdefault(v["ten"], {})["loi"] = luc.isoformat(timespec="seconds")
            tom["loi"].append(v["ten"])
            ghi_ket_qua(thu_muc_bridge, v["ten"], "loi", luc, f"chạy bù lịch {v['hen']}", ma)
    return tom


def bao_cao(kh: dict, tom: dict, luc: datetime) -> str:
    d = [f"# Harness² chạy bù · {luc.strftime('%d/%m/%Y %Hh%M')} (giờ VN)"]
    def muc(tieu_de, ds):
        if ds:
            d.append(f"## {tieu_de}"); d.extend(f"- {x}" for x in ds)
    muc("Đã chạy bù xong", tom["xong"])
    muc("Chạy bù LỖI", tom["loi"])
    muc("Chạy thử (chưa chạy thật)", tom["chay_thu"])
    muc("CHỜ ANH — việc tiền/ngân hàng bị lỡ (không tự chạy)", [f"{v['ten']} (lịch {v['hen']})" for v in kh["chi_bao_tien"]])
    muc("CHỜ ANH — quá cửa sổ chạy bù", [f"{v['ten']} (lịch {v['hen']})" for v in kh["qua_cua_so"]])
    muc("Hoãn vì thiếu RAM", tom["hoan_ram"])
    muc("Hỏng quyền (cấp lại rồi chạy tay)", [f"{q}: {', '.join(ds)}" for q, ds in tom["hong_quyen"].items()])
    if len(d) == 1:
        d.append("Không có việc nào bị lỡ.")
    return "\n".join(d) + "\n"


def ma_thoat(kh: dict, tom: dict) -> int:
    if tom["loi"]:
        return 1
    if kh["chi_bao_tien"] or kh["qua_cua_so"] or tom["hoan_ram"] or tom["hong_quyen"]:
        return 2
    return 0


def kiem_quyen_tu_cau_hinh(cau_hinh: dict) -> dict[str, Callable[[], bool]]:
    """Mỗi quyền là một lệnh kiểm (mã 0 = ổn), do PC khai trong cấu hình."""
    return {q: (lambda l=lenh: chay_lenh(l, 120) == 0) for q, lenh in cau_hinh.get("kiem_quyen", {}).items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--chay-that", action="store_true")
    a = ap.parse_args(argv)
    ch = json.loads(Path(a.config).read_text(encoding="utf-8"))
    thu_muc_tt = Path(ch["thu_muc_trang_thai"]); thu_muc_tt.mkdir(parents=True, exist_ok=True)
    p_tt = thu_muc_tt / TEP_TRANG_THAI
    trang_thai = json.loads(p_tt.read_text(encoding="utf-8")) if p_tt.exists() else {}
    bridge = Path(ch["thu_muc_bridge"]) if ch.get("thu_muc_bridge") else None
    gio = lambda: datetime.now(VN)
    kh = lap_ke_hoach(ch["viec"], trang_thai, gio(), ch.get("cua_so_gio", 12))
    tom = thuc_hien(kh, trang_thai, kiem_quyen_tu_cau_hinh(ch), chay_that=a.chay_that, bay_gio=gio,
                    thu_muc_bridge=bridge if a.chay_that else None)
    if a.chay_that:
        p_tt.write_text(json.dumps(trang_thai, ensure_ascii=False, indent=2), encoding="utf-8")
    bc = bao_cao(kh, tom, gio())
    print(bc)
    if a.chay_that and bridge and (kh["chi_bao_tien"] or kh["qua_cua_so"] or tom["loi"] or tom["hong_quyen"] or tom["hoan_ram"]):
        (bridge / f"ket-qua-PC-H2-CHAY-BU-{gio().strftime('%d %m %Y %Hh%Mp')}.md").write_text(bc, encoding="utf-8")
    return ma_thoat(kh, tom)


if __name__ == "__main__":
    sys.exit(main())
