"""Kiểm tra tồn đọng thật từ 2 tab của sheet "DMV Tong Hop Gia Theo ParentSKU" (xuất CSV). 0 token.

  python ton_dong.py --tong-hop tong-hop.csv --lich-su lich-su.csv --ra ket-qua [--ngay-dong 14]

Trả lời 3 câu:
  1. DỮ LIỆU CÓ CÒN MỚI KHÔNG? (bản chụp cuối quá cũ thì mọi kết luận về "đồng" đều không đáng tin)
  2. Tồn HTsoft mọi kho lớn hơn tồn bán sàn bao nhiêu (tồn nằm ngoài kho bán / thiếu IMEI) — cần kiểm kho thật.
  3. Mã nào có tồn mà số tồn bán sàn KHÔNG ĐỔI suốt N ngày (ứng viên hàng đồng).
Chỉ đọc các cột bán hàng (ParentSKU, tồn, giá lẻ công khai). Bỏ qua mọi cột khác, kể cả cột nội bộ. Giá trị tính bằng giá lẻ,
chỉ là ước tính, KHÔNG phải giá vốn.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

SIM_RE = re.compile(r"^\s*sim\b", re.IGNORECASE)


def parse_number(text: Any) -> int | None:
    s = str(text if text is not None else "").strip().replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):  # kiểu Việt: 1.234.567
        return int(s.replace(".", ""))
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return None


def _col(header: list[str], prefix: str) -> int:
    for i, h in enumerate(header):
        if h.strip().lower().startswith(prefix.lower()):
            return i
    raise ValueError(f"Không thấy cột bắt đầu bằng '{prefix}' (có: {', '.join(header[:8])}...)")


def _rows(path: Path) -> list[list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.reader(f) if any(c.strip() for c in r)]


def load_tong_hop(path: Path) -> dict[str, dict[str, Any]]:
    rows = _rows(path)
    h = rows[0]
    i_sku, i_ten = _col(h, "ParentSKU"), _col(h, "Tên")
    i_san, i_ht, i_gia = _col(h, "Tồn bán sàn"), _col(h, "Tồn HTsoft"), _col(h, "Giá lẻ HTsoft")
    out: dict[str, dict[str, Any]] = {}
    for r in rows[1:]:
        r = r + [""] * (len(h) - len(r))
        sku = r[i_sku].strip()
        if sku:
            out[sku] = {"ten": r[i_ten].strip(), "ban_san": parse_number(r[i_san]), "htsoft": parse_number(r[i_ht]),
                        "gia_le": parse_number(r[i_gia])}
    return out


def load_lich_su(path: Path) -> list[tuple[date, str, int]]:
    rows = _rows(path)
    h = rows[0]
    i_d, i_sku, i_san = _col(h, "Ngày"), _col(h, "ParentSKU"), _col(h, "Tồn bán sàn")
    out = []
    for r in rows[1:]:
        r = r + [""] * (len(h) - len(r))
        qty = parse_number(r[i_san])
        try:
            d = datetime.strptime(r[i_d].strip(), "%Y-%m-%d").date()
        except ValueError:
            continue
        if r[i_sku].strip() and qty is not None:
            out.append((d, r[i_sku].strip(), qty))
    return out


def tinh(
    tong_hop: dict[str, dict[str, Any]],
    lich_su: list[tuple[date, str, int]],
    *,
    hom_nay: date,
    ngay_dong: int = 14,
    cu_ngay: int = 2,
) -> dict[str, Any]:
    canh_bao: list[str] = []
    ngay_cuoi = max((d for d, _, _ in lich_su), default=None)
    ngay_dau = min((d for d, _, _ in lich_su), default=None)
    cu = (hom_nay - ngay_cuoi).days if ngay_cuoi else None
    du_lieu_cu = ngay_cuoi is None or cu > cu_ngay
    if ngay_cuoi is None:
        canh_bao.append("du-lieu-cu: lịch sử rỗng, chưa kết luận được gì về hàng đồng")
    elif du_lieu_cu:
        canh_bao.append(f"du-lieu-cu: bản chụp cuối {ngay_cuoi} đã {cu} ngày trước. Job cập nhật sheet có thể đã dừng. "
                        "Mọi kết luận 'hàng đồng' dưới đây KHÔNG đáng tin cho tới khi sheet chạy lại.")
    if ngay_cuoi and ngay_dau and (ngay_cuoi - ngay_dau).days < ngay_dong:
        canh_bao.append(f"lich-su-ngan: lịch sử chỉ dài {(ngay_cuoi - ngay_dau).days} ngày, ngắn hơn ngưỡng {ngay_dong} ngày")

    by_sku: dict[str, list[tuple[date, int]]] = {}
    for d, sku, qty in lich_su:
        by_sku.setdefault(sku, []).append((d, qty))

    dong, chenh = [], []
    for sku, info in tong_hop.items():
        sim = bool(SIM_RE.match(sku))
        ban_san, ht, gia = info["ban_san"], info["htsoft"], info["gia_le"]
        if ban_san is not None and ht is not None and ht > ban_san:
            c = ht - ban_san
            chenh.append({"sku": sku, "ten": info["ten"], "ban_san": ban_san, "htsoft": ht, "chenh": c,
                          "gia_tri_uoc_tinh": None if sim or gia is None else c * gia, "la_sim": sim})
        series = sorted(by_sku.get(sku, []))
        if ban_san and ban_san > 0 and len(series) >= 2 and not sim:
            cur = series[-1][1]
            start = series[-1][0]
            for d, q in reversed(series):
                if q != cur:
                    break
                start = d
            days = (series[-1][0] - start).days
            if cur == ban_san and days >= ngay_dong:
                dong.append({"sku": sku, "ten": info["ten"], "ban_san": ban_san, "so_ngay_khong_doi": days,
                             "gia_tri_uoc_tinh": None if gia is None else ban_san * gia})
    chenh.sort(key=lambda r: (r["gia_tri_uoc_tinh"] or 0, r["chenh"]), reverse=True)
    dong.sort(key=lambda r: (r["gia_tri_uoc_tinh"] or 0), reverse=True)
    return {
        "hom_nay": hom_nay.isoformat(),
        "ban_chup_cuoi": ngay_cuoi.isoformat() if ngay_cuoi else None,
        "so_ngay_cu": cu,
        "du_lieu_cu": du_lieu_cu,
        "canh_bao": canh_bao,
        "ngay_dong": ngay_dong,
        "chenh_ngoai_san": {"so_ma": len(chenh), "so_may": sum(r["chenh"] for r in chenh),
                            "gia_tri_uoc_tinh": sum(r["gia_tri_uoc_tinh"] or 0 for r in chenh), "danh_sach": chenh},
        "hang_dong": {"so_ma": len(dong), "gia_tri_uoc_tinh": sum(r["gia_tri_uoc_tinh"] or 0 for r in dong), "danh_sach": dong},
    }


def _tr(n: int | None) -> str:
    return "—" if n is None else f"{n / 1e6:,.1f} tr"


def markdown(kq: dict[str, Any], top: int = 20) -> str:
    L = [f"# Kiểm tra tồn đọng — {kq['hom_nay']}", ""]
    if kq["canh_bao"]:
        L += ["## ⚠ Cảnh báo", *[f"- {c}" for c in kq["canh_bao"]], ""]
    c = kq["chenh_ngoai_san"]
    L += [f"## Tồn HTsoft > tồn bán sàn: {c['so_ma']} mã, {c['so_may']} máy, ước tính {_tr(c['gia_tri_uoc_tinh'])} (theo giá lẻ)",
          "Đây là hàng nằm ngoài kho bán sàn hoặc thiếu IMEI: cần kiểm kho thật. SIM không tính giá trị.", "",
          "| Mã | Tồn sàn | Tồn HTsoft | Chênh | ≈ Giá trị |", "|---|---:|---:|---:|---:|"]
    L += [f"| {r['sku']} | {r['ban_san']} | {r['htsoft']} | {r['chenh']} | {_tr(r['gia_tri_uoc_tinh'])} |" for r in c["danh_sach"][:top]]
    d = kq["hang_dong"]
    L += ["", f"## Tồn không đổi ≥ {kq['ngay_dong']} ngày: {d['so_ma']} mã, ước tính {_tr(d['gia_tri_uoc_tinh'])}"]
    if kq["du_lieu_cu"]:
        L.append("(Dữ liệu cũ nên danh sách này không đáng tin.)")
    L += ["", "| Mã | Tồn sàn | Ngày không đổi | ≈ Giá trị |", "|---|---:|---:|---:|"]
    L += [f"| {r['sku']} | {r['ban_san']} | {r['so_ngay_khong_doi']} | {_tr(r['gia_tri_uoc_tinh'])} |" for r in d["danh_sach"][:top]]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # console Windows cp1252 không in được tiếng Việt
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tong-hop", required=True)
    ap.add_argument("--lich-su", required=True)
    ap.add_argument("--ra", required=True, help="thư mục ghi ton-dong.json và ton-dong.md")
    ap.add_argument("--ngay-dong", type=int, default=14)
    ap.add_argument("--hom-nay", help="YYYY-MM-DD (mặc định: hôm nay)")
    args = ap.parse_args(argv)
    try:
        today = datetime.strptime(args.hom_nay, "%Y-%m-%d").date() if args.hom_nay else date.today()
        kq = tinh(load_tong_hop(Path(args.tong_hop)), load_lich_su(Path(args.lich_su)), hom_nay=today, ngay_dong=args.ngay_dong)
    except (OSError, ValueError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    out = Path(args.ra)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ton-dong.json").write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "ton-dong.md").write_text(markdown(kq), encoding="utf-8")
    print(markdown(kq, top=10))
    return 2 if kq["du_lieu_cu"] else 0


if __name__ == "__main__":
    sys.exit(main())
