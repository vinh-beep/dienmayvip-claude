#!/usr/bin/env python3
"""Đọc bảng giá NCC dán từ Telegram (kiểu "MD Samsung") ra CSV chuẩn dmv_GiaNCC.

Cách dùng:
    python doc_bang_gia_telegram.py --ncc "Ten NCC" --ngay 13/10/2026 \
        --vao bang-gia.txt --ra bang-gia.csv

File vào là văn bản dán nguyên từ Telegram. Khối giá bắt đầu bằng dòng tiêu đề có chữ
"Chưa kích" hoặc "Kích Hoạt"/"Đã kích"; mỗi mặt hàng là một dòng bắt đầu bằng "+".

Kết quả chứa giá nhập: KHÔNG đưa vào kho công khai hay Drive (Phần A mục 3 sổ chuẩn).
Chỉ ghi vào SQL `dmv_GiaNCC` trên PC hoặc `D:\\VIP DATA\\02 Bang Gia NCC`.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from dataclasses import dataclass, field

COT = [
    "NgayBaoGia", "NCC", "NhomHang", "TenHang", "Model", "MauSac",
    "LoaiHang", "BaoHanh", "SL_Min", "DonGia_VND", "GhiChu",
]

# Màu: (khoá không dấu, tên chuẩn, các cách viết CÓ DẤU đúng). Một từ chỉ là màu khi viết đúng dấu
# (đen, bạc, hồng, tím, trắng) hoặc hoàn toàn không dấu (Den, Bac) — để "đến", "bậc", "hỏng", "tìm",
# "trạng" không bị nhận nhầm. Cụm 2 từ xếp trước.
MAU = [
    ("xanh duong", "Xanh duong", ("xanh dương",)), ("x duong", "Xanh duong", ("x dương",)),
    ("x blue", "Xanh duong", ()), ("xanh blue", "Xanh duong", ()), ("blue", "Xanh duong", ()),
    ("xanh la", "Xanh la", ("xanh lá",)), ("x la", "Xanh la", ("x lá",)),
    ("xanh", "Xanh", ()), ("den", "Den", ("đen",)), ("tim", "Tim", ("tím",)),
    ("trang", "Trang", ("trắng",)), ("xam", "Xam", ("xám",)),
    ("bac", "Bac", ("bạc",)), ("pink", "Hong", ()), ("hong", "Hong", ("hồng",)), ("vang", "Vang", ("vàng",)),
]
TACH_TU = re.compile(r"([().,:;*/\-\s]+)")


def la_mau(tu_goc: str, khoa: str, co_dau) -> bool:
    t = tu_goc.strip().lower()
    return (t == khoa and bo_dau(t) == t) or t in co_dau


def _duyet_mau(chuoi: str, xoa: bool):
    """Trả về (danh sách màu chuẩn, chuỗi đã xoá màu nếu xoa=True)."""
    manh = [m for m in TACH_TU.split(chuoi) if m != ""]
    ket, ra = [], []
    i = 0
    while i < len(manh):
        t = manh[i]
        if TACH_TU.fullmatch(t):
            ra.append(t); i += 1; continue
        hit = None
        if i + 2 < len(manh) and TACH_TU.fullmatch(manh[i + 1]) and not TACH_TU.fullmatch(manh[i + 2]):
            cum = t + " " + manh[i + 2]
            hit = next((c for k, c, d in MAU if " " in k and la_mau(cum, k, d)), None)
            if hit:
                i += 3
        if hit is None:
            hit = next((c for k, c, d in MAU if " " not in k and la_mau(t, k, d)), None)
            if hit is None:
                ra.append(t); i += 1; continue
            i += 1
        if hit not in ket:
            ket.append(hit)
        ra.append(" ")
    return ket, ("".join(ra) if xoa else chuoi)


GIA_RE = re.compile(r"(?<![\w/])(\d{1,3}(?:\.\d{3})+k?|\d{2,6}k)(?![\w/])", re.IGNORECASE)
SL_RE = re.compile(r"\bsl\s*:?\s*(\d+)?\s*c?\b", re.IGNORECASE)
SL_TRUOC_RE = re.compile(r"\bsl\s*:?\s*(\d+)\s*c?\s*:?\s*$", re.IGNORECASE)
SL_IT_RE = re.compile(r"\bsl\s*(ít|it)\b", re.IGNORECASE)
ROM = r"(32|64|126|128|256|512|1024)"
RAM_ROM_RE = re.compile(r"\(?\s*(2|3|4|6|8|12|16)\s*G?B?\s*/\s*" + ROM + r"\s*G?B?\s*\)?", re.IGNORECASE)
ROM_RE = re.compile(r"(?:\(\s*" + ROM + r"\s*\)|\b" + ROM + r"\s*G\b|\b" + ROM + r"\b)", re.IGNORECASE)
MA_RE = re.compile(r"\b([A-Z]\d{3}[A-Z]?)\b")
MANG = {"4G", "5G", "LTE", "WIFI", "4G LTE"}


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def doc_gia(chuoi: str) -> int:
    """'1.234k' -> 1234000; '12.345' -> 12345000; '555k' -> 555000 (số minh hoạ)."""
    gia = int(chuoi.lower().rstrip("k").replace(".", ""))
    if gia < 100_000:  # NCC ghi theo nghìn đồng
        gia *= 1000
    return gia


@dataclass
class DongHang:
    ten: str
    model: str = ""
    cau_hinh: str = ""
    mau: list[str] = field(default_factory=list)
    gia: list[tuple[int, int]] = field(default_factory=list)  # (SL_Min, DonGia)
    ghi_chu: list[str] = field(default_factory=list)


def tach_dong(dong: str) -> DongHang | None:
    goc = dong.strip().lstrip("\ufeff").strip()
    if not goc.startswith("+"):
        return None
    than = goc[1:].replace("*", " ")

    gias = [(m.start(), m.end(), m.group(1)) for m in GIA_RE.finditer(than)]
    if not gias:
        return None
    dau_gia = gias[0][0]
    sl_dau = 1
    m_sl = SL_TRUOC_RE.search(than[:dau_gia])
    if m_sl:  # "SL 5: 1.100k" ngay trước giá đầu
        sl_dau, dau_gia = int(m_sl.group(1)), m_sl.start()
    gia_list = [(sl_dau, doc_gia(gias[0][2]))]
    gia_le = []
    for i in range(1, len(gias)):
        truoc = SL_IT_RE.sub(" ", than[gias[i - 1][1]:gias[i][0]])  # "SL ít" = sắp hết, không phải bậc
        sl = SL_RE.search(truoc)
        if sl:
            gia_list.append((int(sl.group(1)) if sl.group(1) else 0, doc_gia(gias[i][2])))
        else:
            gia_le.append(gias[i][2])

    phan_ten = than[:dau_gia]
    ch = RAM_ROM_RE.search(phan_ten)
    if ch:
        cau_hinh = f"{ch.group(1)}/{ch.group(2)}"
        phan_ten = RAM_ROM_RE.sub(" ", phan_ten, count=1)
    else:
        rom = ROM_RE.search(phan_ten)
        cau_hinh = (rom.group(1) or rom.group(2) or rom.group(3)) if rom else ""
        if rom:
            phan_ten = phan_ten[:rom.start()] + " " + phan_ten[rom.end():]

    ten = phan_ten.split(":", 1)[0]
    ten = bo_mau(ten.replace("(", " ").replace(")", " "))
    ten = " ".join(ten.replace("/", " ").split()).strip(" -.,")
    model = ""
    m = MA_RE.search(ten.upper())
    if m:
        model = m.group(1)
        con_lai = " ".join(re.sub(r"(?i)\b" + model + r"\b", " ", ten).split()).strip(" -.,")
        if not con_lai or con_lai.upper() in MANG:
            con_lai = (model + " " + con_lai).strip()  # "A076", "X135 4G": tên chính là mã
        ten = con_lai

    mau = tim_mau(GIA_RE.sub(" ", than))

    ghi_chu: list[str] = []
    phan_sau = SL_RE.sub(" ", GIA_RE.sub(" ", than[dau_gia:]))
    phan_sau += " " + phan_ten.split(":", 1)[1] if ":" in phan_ten else ""
    for manh in re.split(r"[-.;:()]", bo_mau(phan_sau)):
        manh = " ".join(bo_dau(manh).split()).strip(" ,")
        if len(manh) >= 3 and manh.lower() not in {"sl", "sl it"} | {m.lower() for m in mau}:
            ghi_chu.append(manh)
    if any(sl == 0 for sl, _ in gia_list):
        ghi_chu.append("SL: NCC khong ghi so - hoi lai")
    if gia_le:
        ghi_chu.append("Gia khac trong dong (khong ro bac): " + ", ".join(gia_le))
        print(f"CANH BAO: dong co gia khong ro bac SL, da ghi vao GhiChu: {goc}", file=sys.stderr)
    ghi_chu = list(dict.fromkeys(ghi_chu))

    return DongHang(ten=ten, model=model, cau_hinh=cau_hinh, mau=mau, gia=gia_list, ghi_chu=ghi_chu)


def tim_mau(chuoi: str) -> list[str]:
    return _duyet_mau(chuoi, False)[0]


def bo_mau(chuoi: str) -> str:
    return " ".join(bo_dau(_duyet_mau(chuoi, True)[1]).split())


def doc_van_ban(van_ban: str) -> list[tuple[str, DongHang]]:
    """Trả về [(LoaiHang, DongHang)] theo khối 'Chưa kích' / 'Đã kích'."""
    loai = "Chua ro"
    ket = []
    for dong in van_ban.splitlines():
        thap = bo_dau(dong).lower()
        if not dong.strip().startswith("+"):
            t = thap.strip()
            la_tieu_de = len(t) <= 80 and not t.startswith(("luu y", "chu y", "note"))
            if la_tieu_de and "chua kich" in t:
                loai = "Chua kich hoat"
            elif la_tieu_de and ("kich hoat" in t or "da kich" in t):
                loai = "Da kich hoat"
            continue
        dh = tach_dong(dong)
        if dh:
            ket.append((loai, dh))
    return ket


def ra_csv(cac_dong, ncc: str, ngay: str, nhom: str = "Dien thoai") -> list[dict]:
    hang = []
    for loai, dh in cac_dong:
        ten = dh.ten + (f" ({dh.cau_hinh})" if dh.cau_hinh else "")
        for sl_min, gia in dh.gia:
            hang.append({
                "NgayBaoGia": ngay, "NCC": ncc, "NhomHang": nhom, "TenHang": ten,
                "Model": dh.model, "MauSac": "/".join(dh.mau), "LoaiHang": loai,
                "BaoHanh": "", "SL_Min": sl_min, "DonGia_VND": gia,
                "GhiChu": "; ".join(dh.ghi_chu),
            })
    return hang


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ncc", required=True)
    p.add_argument("--ngay", required=True, help="dd/mm/yyyy")
    p.add_argument("--nhom", default="Dien thoai")
    p.add_argument("--vao", required=True)
    p.add_argument("--ra", required=True)
    a = p.parse_args(argv)
    with open(a.vao, encoding="utf-8-sig") as f:
        van_ban = f.read()
    hang = ra_csv(doc_van_ban(van_ban), a.ncc, a.ngay, a.nhom)
    with open(a.ra, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COT)
        w.writeheader()
        w.writerows(hang)
    print(f"Ghi {len(hang)} dong gia -> {a.ra}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
