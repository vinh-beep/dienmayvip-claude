"""In tem QR khổ A4 từ danh sách CSV — chạy trên PC, 0 token.

CSV cột: sku,ten,cn,ke,nguon   (nguon: tem | poster | standee | wobbler | bh)
Ví dụ:   python tao_tem.py danh-sach.csv https://qr.dienmayvip.com tem-30LL.pdf

Tem chỉ in TÊN + MÃ QR, không in giá: giá đổi theo live, in giá lên tem sẽ lệch (cổng lệch giá).
"""
from __future__ import annotations

import csv
import io
import sys
import textwrap
from urllib.parse import urlencode

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app import CHI_NHANH, KE_RE, NGUON, SKU_RE

COT, HANG = 3, 6
O_RONG, O_CAO = 60 * mm, 44 * mm
LE_TRAI, LE_TREN = (A4[0] - COT * O_RONG) / 2, 12 * mm

# Phông có dấu tiếng Việt: Windows (Arial) trước, rồi Linux (DejaVu).
PHONG = [
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def dang_ky_phong() -> tuple[str, str]:
    for thuong, dam in PHONG:
        try:
            pdfmetrics.registerFont(TTFont("VN", thuong))
            pdfmetrics.registerFont(TTFont("VN-Dam", dam))
            return "VN", "VN-Dam"
        except Exception:
            continue
    raise SystemExit("Không tìm thấy phông có dấu tiếng Việt (Arial hoặc DejaVu)")


def tao_link(goc: str, sku: str, cn: str, ke: str, nguon: str) -> str:
    tham_so = {"sku": sku, "cn": cn, "nguon": nguon}
    if ke:
        tham_so["ke"] = ke
    return f"{goc.rstrip('/')}/?{urlencode(tham_so)}"


def doc_danh_sach(tep: str) -> list[dict[str, str]]:
    dong_hop_le, loi = [], []
    with open(tep, encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            r = {k: (v or "").strip() for k, v in r.items()}
            if not SKU_RE.match(r.get("sku", "")):
                loi.append(f"dòng {i}: sku sai")
            elif r.get("cn") not in CHI_NHANH:
                loi.append(f"dòng {i}: chi nhánh '{r.get('cn')}' không có trong {list(CHI_NHANH)}")
            elif r.get("ke") and not KE_RE.match(r["ke"]):
                loi.append(f"dòng {i}: kệ sai")
            elif r.get("nguon", "tem") not in NGUON:
                loi.append(f"dòng {i}: nguồn sai")
            else:
                r.setdefault("nguon", "tem")
                r["nguon"] = r["nguon"] or "tem"
                dong_hop_le.append(r)
    if loi:
        raise SystemExit("Danh sách lỗi, chưa in:\n  " + "\n  ".join(loi))
    return dong_hop_le


def in_pdf(danh_sach: list[dict[str, str]], goc: str, tep_ra: str) -> int:
    thuong, dam = dang_ky_phong()
    c = canvas.Canvas(tep_ra, pagesize=A4)
    for i, r in enumerate(danh_sach):
        vi_tri = i % (COT * HANG)
        if i and vi_tri == 0:
            c.showPage()
        x = LE_TRAI + (vi_tri % COT) * O_RONG
        y = A4[1] - LE_TREN - (vi_tri // COT + 1) * O_CAO
        anh = qrcode.make(tao_link(goc, r["sku"], r["cn"], r.get("ke", ""), r["nguon"]), box_size=6, border=1)
        buf = io.BytesIO()
        anh.save(buf, format="PNG")
        buf.seek(0)
        c.rect(x + 1 * mm, y + 1 * mm, O_RONG - 2 * mm, O_CAO - 2 * mm)
        c.drawImage(ImageReader(buf), x + 3 * mm, y + 6 * mm, 32 * mm, 32 * mm)
        c.setFont(dam, 7)
        c.drawString(x + 37 * mm, y + 34 * mm, "QUÉT ĐỂ XEM")
        c.drawString(x + 37 * mm, y + 30 * mm, "GIÁ & TƯ VẤN")
        c.setFont(thuong, 6)
        ten = r.get("ten", r["sku"])
        for j, dong in enumerate(textwrap.wrap(ten, 14)[:4]):
            c.drawString(x + 37 * mm, y + (24 - j * 4) * mm, dong)
        c.drawString(x + 37 * mm, y + 6 * mm, (CHI_NHANH[r["cn"]] + (" · Kệ " + r["ke"] if r.get("ke") else "")).strip())
    c.save()
    return len(danh_sach)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    so = in_pdf(doc_danh_sach(sys.argv[1]), sys.argv[2], sys.argv[3])
    print(f"Đã in {so} tem vào {sys.argv[3]}")
