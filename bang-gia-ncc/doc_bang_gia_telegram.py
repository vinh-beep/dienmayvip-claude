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

# Màu hay gặp trong tin NCC (không dấu, chữ thường). Cụm dài xếp trước.
MAU = [
    ("xanh duong", "Xanh duong"), ("x duong", "Xanh duong"), ("x blue", "Xanh duong"),
    ("xanh blue", "Xanh duong"), ("blue", "Xanh duong"),
    ("xanh la", "Xanh la"), ("x la", "Xanh la"),
    ("xanh", "Xanh"), ("den", "Den"), ("tim", "Tim"), ("trang", "Trang"), ("xam", "Xam"),
    ("bac", "Bac"), ("pink", "Hong"), ("hong", "Hong"), ("vang", "Vang"),
]

# Giá: "5.360k", "16.890", "990k". Số trơn không có "k" (vd 128, 256) KHÔNG phải giá.
GIA_RE = re.compile(r"(?<![\w/])(\d{1,3}(?:\.\d{3})+k?|\d{2,6}k)(?![\w/])", re.IGNORECASE)
SL_RE = re.compile(r"\bsl\s*:?\s*(\d+)?\s*c?\b", re.IGNORECASE)
RAM_ROM_RE = re.compile(r"\(?\s*(\d+)\s*G?B?\s*/\s*(\d+)\s*G?B?\s*\)?", re.IGNORECASE)
ROM_RE = re.compile(r"(?:\(\s*(\d{2,4})\s*\)|\b(\d{2,4})\s*G\b|\b(32|64|126|128|256|512|1024)\b)", re.IGNORECASE)
MA_RE = re.compile(r"\b([A-Z]\d{3}[A-Z]?)\b")
MANG = {"4G", "5G", "LTE", "WIFI", "4G LTE"}


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def doc_gia(chuoi: str) -> int:
    """'5.360k' -> 5360000; '16.890' -> 16890000; '990k' -> 990000."""
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


def tim_mau(chuoi: str) -> list[str]:
    text = " " + " ".join(re.sub(r"[().,:;*/-]", " ", bo_dau(chuoi).lower()).split()) + " "
    ket: list[str] = []
    for khoa, chuan in MAU:
        if " " + khoa + " " in text:
            if chuan not in ket:
                ket.append(chuan)
            text = text.replace(" " + khoa + " ", " ")
    return ket


def bo_mau(chuoi: str) -> str:
    text = " " + " ".join(bo_dau(chuoi).split()) + " "
    for khoa, _ in MAU:
        text = re.sub(r"(?i)(?<=[ .,(/:])" + re.escape(khoa) + r"(?=[ .,)/:])", " ", text)
    return " ".join(text.split())


def tach_dong(dong: str) -> DongHang | None:
    goc = dong.strip()
    if not goc.startswith("+"):
        return None
    than = goc[1:].replace("*", " ")

    gias = [(m.start(), m.end(), m.group(1)) for m in GIA_RE.finditer(than)]
    if not gias:
        return None
    gia_list = [(1, doc_gia(gias[0][2]))]
    for i in range(1, len(gias)):
        truoc = than[gias[i - 1][1]:gias[i][0]]
        sl = SL_RE.search(truoc)
        if sl:
            gia_list.append((int(sl.group(1)) if sl.group(1) else 0, doc_gia(gias[i][2])))
    dau_gia = gias[0][0]

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
    ghi_chu = list(dict.fromkeys(ghi_chu))

    return DongHang(ten=ten, model=model, cau_hinh=cau_hinh, mau=mau, gia=gia_list, ghi_chu=ghi_chu)


def doc_van_ban(van_ban: str) -> list[tuple[str, DongHang]]:
    """Trả về [(LoaiHang, DongHang)] theo khối 'Chưa kích' / 'Đã kích'."""
    loai = "Chua ro"
    ket = []
    for dong in van_ban.splitlines():
        thap = bo_dau(dong).lower()
        if not dong.strip().startswith("+"):
            if "chua kich" in thap:
                loai = "Chua kich hoat"
            elif "kich hoat" in thap or "da kich" in thap:
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
    with open(a.vao, encoding="utf-8") as f:
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
