"""Tổng kết tự động mọi tin trên Bridge thành MỘT bảng theo danh mục (kiểu Lark Mail VIP), có khối SAO CHÉP TOÀN BỘ.

Đọc: tin-*.json · ket-qua-*.json · ket-qua-*.md · luat-*.json trong thư mục Bridge (cửa sổ mặc định 24 giờ).
Ghi: TONG-KET-TU-DONG-<dd MM yyyy HHhmmp>.md + TONG-KET-TU-DONG-moi-nhat.md (+ .json cho app .exe đọc).
Danh mục: GAP (cần anh) · LOI (lỗi, kèm cách chữa từ loi_biet.json) · XONG · LUAT · KHAC.
Không gọi AI → 0 token. Che SĐT/email/CCCD/số tài khoản. Chạy lại cùng dữ liệu ra cùng kết quả (idempotent).
  python tong_ket.py --bridge "C:\\DMV-Cloud-Bridge" [--gio 24] [--ra <thư mục>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN = timezone(timedelta(hours=7))
DAY = Path(__file__).resolve().parent
RE_TS_TEN = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})")          # tin-2026-10-26T19-01__...
RE_TS_VN = re.compile(r"(\d{2}) (\d{2}) (\d{4}) (\d{2})h(\d{2})p")              # ...-26 10 2026 19h10p.md
RE_GAP = re.compile(r"GẤP|KHẨN|cần anh|chờ anh|anh duyệt|chuyen-anh|CHỜ XEM|can_xac_nhan", re.I)
RE_LOI = re.compile(r"lỗi|loi\b|FAILED|cảnh báo|\(ma \d+\)|invalid_grant|unreachable|disabled", re.I)
RE_XONG = re.compile(r"\bXONG\b|ĐẠT|hoàn tất|đã xong|COMPLETED", re.I)
# Che thông tin cá nhân / tài khoản. Không ghi nội dung khớp ra đâu cả.
CHE = [
    (re.compile(r"(?<!\d)(?:\+84|0)(?:\d[ .]?){9}(?!\d)"), "[SĐT]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"(?<!\d)\d{12}(?!\d)"), "[CCCD]"),
    (re.compile(r"(?i)(stk|số tài khoản|tài khoản)\s*[:#]?\s*\d{6,}"), r"\1 [tài khoản]"),
]


def che(s: str) -> str:
    for r, t in CHE:
        s = r.sub(t, s)
    return s


def gio_tu_ten(ten: str) -> datetime | None:
    m = RE_TS_TEN.search(ten)
    if m:
        y, mo, d, h, mi = map(int, m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=VN)
    m = RE_TS_VN.search(ten)
    if m:
        d, mo, y, h, mi = map(int, m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=VN)
    return None


RE_LUC_JSON = re.compile(r"(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})")                # "luc": "26/10/2026 11:28"


def gio_tep(p: Path) -> datetime:
    t = gio_tu_ten(p.name)
    if t:
        return t
    if p.suffix == ".json":
        try:
            m = RE_LUC_JSON.search(str(json.loads(p.read_text(encoding="utf-8-sig")).get("luc", "")))
            if m:
                d, mo, y, h, mi = map(int, m.groups())
                return datetime(y, mo, d, h, mi, tzinfo=VN)
        except (OSError, ValueError, AttributeError):
            pass
    return datetime.fromtimestamp(p.stat().st_mtime, VN)


def nap_loi_biet(duong: Path | None = None) -> dict:
    p = duong or DAY / "loi_biet.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {k.lower(): v for k, v in d.items() if not k.startswith("_")}


def gan_cach_chua(noi_dung: str, loi_biet: dict) -> list[str]:
    nd = noi_dung.lower()
    return [f"{k}: {v['nghia']} → {v['chua']}" for k, v in loi_biet.items() if k in nd]


def doc_tep(p: Path) -> dict | None:
    """Trả về {'tu','chu_de','noi_dung','loai','can_anh'} hoặc None nếu không đọc được."""
    ten = p.name
    try:
        if p.suffix == ".json":
            d = json.loads(p.read_text(encoding="utf-8-sig"))
            if ten.startswith("luat-"):
                return {"tu": d.get("tu", "?"), "chu_de": d.get("id", ten), "loai": "LUAT", "can_anh": False,
                        "noi_dung": " ".join(d.get("noi_dung", []))}
            if ten.startswith("tin-"):
                nd = d.get("noiDung", [])
                nd = " ".join(nd) if isinstance(nd, list) else str(nd)
                return {"tu": d.get("from", "?"), "chu_de": d.get("chu_de", ten), "loai": d.get("type", "tin"),
                        "can_anh": bool(d.get("can_xac_nhan")), "noi_dung": nd}
            if ten.startswith("ket-qua-"):
                nd = " | ".join(str(d.get(k, "")) for k in ("da_lam", "con_lai") if d.get(k))
                return {"tu": d.get("tu", "?"), "chu_de": d.get("chu_de", ten), "loai": "ket-qua",
                        "can_anh": str(d.get("trang_thai", "")).startswith("chuyen-anh") or bool(d.get("con_lai")),
                        "noi_dung": nd}
            return None
        if p.suffix == ".md" and ten.startswith("ket-qua-"):
            dong = [x.strip() for x in p.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
            # Lấy tiêu đề + các dòng nằm dưới mục "cần anh/chờ anh/giao PC" (tối đa 12 dòng).
            lay, bat = [], False
            for x in dong[1:]:
                if x.startswith("#"):
                    bat = bool(RE_GAP.search(x) or re.search(r"Giao PC|Lỗi|Phát hiện|cần biết", x, re.I))
                    continue
                if bat and len(lay) < 12:
                    lay.append(x.lstrip("-*0123456789. "))
            tu = re.search(r"ket-qua-([A-Za-z]+)", ten)
            return {"tu": tu.group(1) if tu else "?", "chu_de": ten.replace(".md", ""), "loai": "ket-qua",
                    "can_anh": bool(lay), "noi_dung": " | ".join(lay) or dong[0].lstrip("# ")}
    except (OSError, ValueError):
        return None
    return None


def phan_loai(m: dict) -> str:
    if m["loai"] == "LUAT":
        return "LUAT"
    nd = m["noi_dung"]
    if m["can_anh"] or m["loai"] == "viec" or RE_GAP.search(nd):
        return "GAP"
    if "trang-thai-he-thong" in m["chu_de"] and re.search(r"\b0 cảnh báo", nd):
        return "XONG"
    if RE_LOI.search(nd):
        return "LOI"
    if RE_XONG.search(nd):
        return "XONG"
    return "KHAC"


def khoa_trung(m: dict) -> str:
    """Cùng chủ đề + cùng 60 ký tự đầu nội dung = một việc, giữ bản mới nhất."""
    return m["chu_de"].split("__")[-1][:40].lower() + "|" + re.sub(r"\d{1,2}[:h]\d{2}", "", m["noi_dung"])[:60].lower()


def gom(bridge: Path, luc: datetime, gio: float = 24, loi_biet: dict | None = None) -> dict:
    loi_biet = nap_loi_biet() if loi_biet is None else loi_biet
    tu_luc = luc - timedelta(hours=gio)
    muc: dict[str, dict] = {}
    for p in sorted(bridge.iterdir(), key=gio_tep):
        if not p.is_file() or p.name.startswith("TONG-KET-TU-DONG"):
            continue
        t = gio_tep(p)
        if t < tu_luc:          # không chặn "tương lai": giờ PC và giờ Drive có thể lệch nhau
            continue
        m = doc_tep(p)
        if not m or not m["noi_dung"].strip():
            continue
        m["noi_dung"] = che(m["noi_dung"].strip())
        m["luc"] = t
        m["tep"] = p.name
        m["danh_muc"] = phan_loai(m)
        m["chua"] = gan_cach_chua(m["noi_dung"], loi_biet)
        muc[khoa_trung(m)] = m          # sorted theo giờ → bản sau đè bản trước
    ra = {"GAP": [], "LOI": [], "XONG": [], "LUAT": [], "KHAC": []}
    for m in muc.values():
        ra[m["danh_muc"]].append(m)
    for k in ra:
        ra[k].sort(key=lambda x: x["luc"], reverse=True)
    return ra


TEN_MUC = {"GAP": "① GẤP — cần anh", "LOI": "② LỖI — kèm cách chữa", "XONG": "③ ĐÃ XONG / ổn",
           "LUAT": "④ LUẬT mới", "KHAC": "⑤ Khác"}


def dong_mot(m: dict, dai: int = 400) -> str:
    nd = m["noi_dung"]
    nd = nd if len(nd) <= dai else nd[:dai].rstrip() + "…"
    return f"{m['luc'].strftime('%d/%m %Hh%M')} · {m['tu']} · {nd}"


def viet_md(ra: dict, luc: datetime, gio: float) -> str:
    d = [f"# TỔNG KẾT TỰ ĐỘNG — {luc.strftime('%d/%m/%Y %Hh%M')} (giờ VN) · {int(gio)} giờ qua",
         f"Gộp {sum(len(v) for v in ra.values())} mục từ Bridge, đã loại trùng, đã che SĐT/email/tài khoản.", ""]
    # Khối sao chép toàn bộ: mỗi mục 1 dòng, có STT, dán được vào Zalo/Lark.
    d += ["## KHỐI SAO CHÉP TOÀN BỘ", "```"]
    stt = 0
    for k in ("GAP", "LOI", "XONG", "LUAT", "KHAC"):
        if not ra[k]:
            continue
        d.append(f"[{TEN_MUC[k]}]")
        for m in ra[k]:
            stt += 1
            d.append(f"{stt}. {dong_mot(m, 220)}")
            for c in m["chua"]:
                d.append(f"   → {c}")
    d += ["```", ""]
    for k in ("GAP", "LOI", "XONG", "LUAT", "KHAC"):
        d.append(f"## {TEN_MUC[k]} ({len(ra[k])})")
        if not ra[k]:
            d.append("- (không có)")
        for m in ra[k]:
            d.append(f"- **{m['chu_de'].split('__')[-1]}** · {dong_mot(m)}  \n  _tệp: {m['tep']}_")
            for c in m["chua"]:
                d.append(f"  - 🔧 {c}")
        d.append("")
    return "\n".join(d) + "\n"


def viet_json(ra: dict) -> str:
    return json.dumps({k: [{"luc": m["luc"].isoformat(timespec="minutes"), "tu": m["tu"], "chu_de": m["chu_de"],
                            "noi_dung": m["noi_dung"], "chua": m["chua"], "tep": m["tep"]} for m in v]
                       for k, v in ra.items()}, ensure_ascii=False, indent=1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bridge", required=True)
    ap.add_argument("--gio", type=float, default=24)
    ap.add_argument("--ra", help="thư mục ghi; mặc định = --bridge")
    ap.add_argument("--luc", help="giờ VN ISO để chạy lại đúng kết quả cũ (kiểm thử)")
    a = ap.parse_args(argv)
    bridge = Path(a.bridge)
    luc = datetime.fromisoformat(a.luc).astimezone(VN) if a.luc else datetime.now(VN)
    ra = gom(bridge, luc, a.gio)
    thu_muc = Path(a.ra) if a.ra else bridge
    thu_muc.mkdir(parents=True, exist_ok=True)
    md = viet_md(ra, luc, a.gio)
    (thu_muc / f"TONG-KET-TU-DONG-{luc.strftime('%d %m %Y %Hh%Mp')}.md").write_text(md, encoding="utf-8")
    (thu_muc / "TONG-KET-TU-DONG-moi-nhat.md").write_text(md, encoding="utf-8")
    (thu_muc / "TONG-KET-TU-DONG-moi-nhat.json").write_text(viet_json(ra), encoding="utf-8")
    print({k: len(v) for k, v in ra.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
