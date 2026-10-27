"""Gom việc gấp / đang làm / chờ anh từ MỌI app (tin JSON trên Bridge, ket-qua, ghi chú .md có frontmatter)
rồi tổng kết theo danh mục kiểu Lark Mail. Mã thuần, 0 token, không cần API nào.

  python tong_hop_viec.py --nguon "G:\\My Drive\\DMV-Cloud-Bridge" --nguon "D:\\Obsidian Vault DMV\\03 Viec" --ra ket-qua
  python tong_hop_viec.py ... --treo-gio 6      # tin gửi quá 6 giờ chưa có ket-qua = TREO

Ghi: tong-hop-<ngày>.md (có khối "CHÉP TẤT CẢ"), tong-hop-<ngày>.json, tong-hop-index.md (liên kết mọi bản tổng hợp).
Che: SĐT, số tài khoản, dòng có giá vốn/NCC rẻ → "[che]" vì bản tổng hợp hay được chép đưa cho AI khác.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

VN = timezone(timedelta(hours=7))
TRANG_THAI = ("gap", "cho-anh", "treo", "canh-bao", "dang-lam", "xong", "khac")
NHAN = {"gap": "🔴 Gấp", "cho-anh": "⏳ Chờ anh", "treo": "🕳 Treo (chưa có kết quả)", "canh-bao": "⚠ Cảnh báo",
        "dang-lam": "🟡 Đang làm", "xong": "✅ Xong", "khac": "📄 Khác"}
DANH_MUC = {
    "tai-chinh": ("Tài chính · Ngân hàng · HĐĐT", r"ngân hàng|ngan hang|sổ phụ|hđđt|hddt|hóa đơn|hoa don|bidv|acb|sacombank|lpbank|vietcombank|giải ngân|thuế|misa"),
    "gia-bg": ("Giá · Báo giá · NCC", r"\bbg\b|báo giá|bao gia|\bncc\b|giá sỉ|gia si|giá lẻ|đổi giá|doi gia|chợ lớn|cho lon|parentsku"),
    "ton-kho": ("Tồn kho · Sản phẩm", r"tồn|ton kho|imei|sell-in|model mới|catalog|mathang"),
    "video-mxh": ("Video · MXH · Nhạc", r"video|tiktok|youtube|facebook|shopee|lazada|nhạc|nhac|suno|thumbnail|câu mở|cau mo|postiz|bigseller"),
    "email-chuong": ("Hộp mail · Chuông · Thông báo", r"hộp mail|hop mail|gmail|lark|chuông|chuong|thông báo|thong bao|zalo"),
    "ai-hatang": ("AI · Harness² · Hạ tầng · App", r"harness|claude|gemini|agent|mod\b|mcp|api|task|tác vụ|tac vu|app\b|\.exe|\.py|cc sync|sync|drive|github|sheet|script|everything"),
}
MAU_SDT = re.compile(r"(?<!\d)(?:\+?84|0)[ .]?[35789](?:[ .]?\d){8}(?!\d)")
MAU_STK = re.compile(r"(?:s[oố][_\- ]?(?:tk|t[aà]i[_\- ]?kho[aả]n)|account)[^\d\n]{0,12}\d{8,16}", re.IGNORECASE)
MAU_NOI_BO = re.compile(r"gi[aá][_\- ]?v[oố]n|gi[aá][_\- ]?nh[aậ]p|ncc[_\- ]?r[eẻ][_\- ]?nh[aấ]t|giasi_?renhat|lãi gộp|lai gop", re.IGNORECASE)
MAU_NGAY = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
MAU_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass
class Muc:
    id: str
    tep: str
    loai: str            # tin | ket-qua | ghi-chu
    ts: str              # ISO giờ VN, rỗng nếu không biết
    tieu_de: str
    danh_muc: str
    trang_thai: str
    nguon: str = ""      # phiên/app gửi
    chu_de: str = ""     # khoá nối tin ↔ ket-qua
    tags: list[str] = field(default_factory=list)
    tom_tat: str = ""    # ≤ 300 ký tự đã che


# ---------------------------------------------------------------- che dữ liệu nhạy cảm


def che(text: str) -> str:
    out = []
    for line in text.splitlines():
        if MAU_NOI_BO.search(line):
            out.append("[che: dòng có giá nội bộ]")
            continue
        line = MAU_STK.sub("[che: số TK]", line)
        line = MAU_SDT.sub("[che: SĐT]", line)
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- phân loại


def phan_loai_trang_thai(tieu_de: str, than: str = "", loai: str = "") -> str:
    t = (tieu_de + " " + than[:400]).lower()
    if loai == "ket-qua" and ("chuyen-anh" in t or "chờ anh" in t or "cho anh" in t):
        return "cho-anh"
    if "🔴" in tieu_de or "khẩn" in t or "khan " in t or "gấp" in t or "báo động" in t or "bao dong" in t:
        return "gap"
    if "chờ anh" in t or "cho anh bam" in t or "anh cần bấm" in t or "chuyen-anh" in t or "cần anh" in t:
        return "cho-anh"
    if "⚠" in tieu_de or "cảnh báo" in t or "canh bao" in t or "lỗi" in tieu_de.lower() or "không đồng bộ" in t:
        return "canh-bao"
    if "✅" in tieu_de or "xong" in tieu_de.lower() or "đã làm" in tieu_de.lower():
        return "xong"
    if "🟡" in tieu_de or "đang làm" in t or "đang sửa" in t or "đang dựng" in t or "dang lam" in t:
        return "dang-lam"
    return "khac"


def phan_loai_danh_muc(tieu_de: str, tags: Iterable[str], chu_de: str = "", than: str = "") -> str:
    for tag in tags:
        tag = str(tag).lower()
        if tag.startswith("chủ-đề/") or tag.startswith("chu-de/"):
            key = tag.split("/", 1)[1]
            for dm, (_, _) in DANH_MUC.items():
                if key.replace("ả", "a") in dm or dm.split("-")[0] in key:
                    return dm
            if "tài-chính" in key or "hđđt" in key or "thuế" in key:
                return "tai-chinh"
            if "giá" in key or "bao-gia" in key:
                return "gia-bg"
            if "kho-ảnh" in key or "marketing" in key or "media" in key:
                return "video-mxh"
            if "chuông" in key or "mail" in key or "thong-bao" in key:
                return "email-chuong"
            if "ai" in key or "hạ-tầng" in key or "ha-tang" in key or "htsoft" in key:
                return "ai-hatang"
    text = f"{chu_de} {tieu_de} {' '.join(map(str, tags))} {than[:300]}".lower()
    best, best_n = "khac", 0
    for dm, (_, rx) in DANH_MUC.items():
        n = len(re.findall(rx, text))
        if n > best_n:
            best, best_n = dm, n
    return best


# ---------------------------------------------------------------- đọc tệp


def doc_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = MAU_FM.match(text)
    if not m:
        return {}, text
    fm: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            fm[k.strip()] = [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
        else:
            fm[k.strip()] = v.strip('"\'')
    return fm, text[m.end():]


def _ts_tu_ten(name: str, mtime: float) -> str:
    m = MAU_NGAY.search(name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00+07:00"
    return datetime.fromtimestamp(mtime, VN).isoformat(timespec="seconds")


def _chuan_ts(value: Any, fallback: str) -> str:
    s = str(value or "").strip()
    if not s:
        return fallback
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=VN)
        return d.astimezone(VN).isoformat(timespec="seconds")
    except ValueError:
        return fallback


def doc_json(path: Path) -> Muc | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    name = path.name.lower()
    loai = "ket-qua" if name.startswith("ket-qua") else "tin"
    noi = data.get("noiDung") or data.get("noi_dung") or data.get("da_lam") or ""
    than = "\n".join(map(str, noi)) if isinstance(noi, list) else str(noi)
    than += "\n" + str(data.get("con_lai") or "")
    chu_de = str(data.get("chu_de") or data.get("task_id") or "")
    tieu_de = str(data.get("tieu_de") or chu_de or path.stem)
    tags = list(data.get("tags") or [])
    trang_thai_raw = str(data.get("trang_thai") or "")
    tt = phan_loai_trang_thai(f"{tieu_de} {trang_thai_raw}", than, loai)
    return Muc(
        id=str(data.get("id") or path.stem), tep=str(path), loai=loai,
        ts=_chuan_ts(data.get("ts") or data.get("created_at") or data.get("luc"), _ts_tu_ten(path.name, path.stat().st_mtime)),
        tieu_de=che(tieu_de)[:160], danh_muc=phan_loai_danh_muc(tieu_de, tags, chu_de, than), trang_thai=tt,
        nguon=str(data.get("from") or data.get("tu") or ""), chu_de=chu_de, tags=[str(t) for t in tags],
        tom_tat=che(than.strip())[:300],
    )


def doc_md(path: Path) -> Muc | None:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    fm, than = doc_frontmatter(text)
    tieu_de = str(fm.get("tieu_de") or path.stem)
    tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
    loai = "ket-qua" if path.name.lower().startswith("ket-qua") else "ghi-chu"
    tt = phan_loai_trang_thai(tieu_de, than, loai)
    if str(fm.get("loai", "")) == "tri-thuc" and tt == "khac":
        tt = "xong"  # tinh hoa / luật đã chốt = không phải việc mở
    return Muc(
        id=str(fm.get("id") or path.stem), tep=str(path), loai=loai,
        ts=_chuan_ts(fm.get("ts"), _ts_tu_ten(path.name, path.stat().st_mtime)),
        tieu_de=che(tieu_de)[:160], danh_muc=phan_loai_danh_muc(tieu_de, tags, str(fm.get("chu_de", "")), than),
        trang_thai=tt, nguon=str(fm.get("nguon") or ""), chu_de=str(fm.get("chu_de") or ""),
        tags=[str(t) for t in tags], tom_tat=che(than.strip())[:300],
    )


def quet(nguon: Iterable[Path], *, tu_ngay: datetime | None = None, toi_da: int = 5000) -> list[Muc]:
    out: list[Muc] = []
    for root in nguon:
        root = Path(root)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in ("_done", "node_modules", "__pycache__")]
            for fn in filenames:
                p = Path(dirpath) / fn
                low = fn.lower()
                if low.endswith(".json") and (low.startswith("tin-") or low.startswith("ket-qua") or "__task__" in low or "__viec__" in low):
                    m = doc_json(p)
                elif low.endswith(".md"):
                    m = doc_md(p)
                else:
                    continue
                if m is None:
                    continue
                if tu_ngay and m.ts and datetime.fromisoformat(m.ts) < tu_ngay:
                    continue
                out.append(m)
                if len(out) >= toi_da:
                    return out
    return out


# ---------------------------------------------------------------- nối tin ↔ kết quả, phát hiện treo


def noi_ket_qua(muc: list[Muc], *, bay_gio: datetime, treo_gio: float) -> list[Muc]:
    co_ket_qua = {m.chu_de for m in muc if m.loai == "ket-qua" and m.chu_de}
    co_ket_qua |= {re.sub(r"^ket-qua-[^-]+-", "", m.id) for m in muc if m.loai == "ket-qua"}
    for m in muc:
        if m.loai != "tin" or m.trang_thai in ("xong", "cho-anh"):
            continue
        if m.chu_de and (m.chu_de in co_ket_qua or any(m.chu_de in k for k in co_ket_qua)):
            m.trang_thai = "xong"
            continue
        try:
            gui_luc = datetime.fromisoformat(m.ts)
        except ValueError:
            continue
        if bay_gio - gui_luc > timedelta(hours=treo_gio) and m.trang_thai in ("khac", "dang-lam"):
            m.trang_thai = "treo"
        elif m.trang_thai == "khac":
            m.trang_thai = "dang-lam"  # tin đã gửi, chưa có kết quả, chưa quá hạn = đang chờ xử lý
    return muc


# ---------------------------------------------------------------- tổng kết


def tong_ket(muc: list[Muc]) -> dict[str, Any]:
    theo_dm: dict[str, dict[str, Any]] = {}
    for dm, (nhan, _) in list(DANH_MUC.items()) + [("khac", ("Khác", ""))]:
        items = sorted((m for m in muc if m.danh_muc == dm), key=lambda m: (m.ts, m.tieu_de), reverse=True)
        if not items:
            continue
        theo_dm[dm] = {"nhan": nhan, "so": len(items), "theo_trang_thai": dict(Counter(m.trang_thai for m in items)),
                       "muc": [asdict(m) for m in items]}
    tong = len(muc)
    mo = sum(m.trang_thai in ("gap", "cho-anh", "treo", "canh-bao", "dang-lam") for m in muc)
    return {"tong": tong, "con_mo": mo, "xong": sum(m.trang_thai == "xong" for m in muc),
            "ti_le_xong": round(100 * (tong - mo) / tong) if tong else 0,
            "theo_trang_thai": dict(Counter(m.trang_thai for m in muc)), "danh_muc": theo_dm}


def _dong(m: dict[str, Any]) -> str:
    ts = m["ts"][:16].replace("T", " ") if m["ts"] else "—"
    nguon = f" · {m['nguon']}" if m["nguon"] else ""
    return f"- {NHAN[m['trang_thai']].split(' ', 1)[0]} {ts}{nguon} — {m['tieu_de']}"


def markdown(kq: dict[str, Any], *, ngay: str, chi_tiet: bool = True) -> str:
    L = [f"# Tổng hợp việc — {ngay}", "",
         f"**{kq['tong']}** mục · còn mở **{kq['con_mo']}** · xong {kq['xong']} ({kq['ti_le_xong']}%)",
         " · ".join(f"{NHAN[k]} {v}" for k, v in sorted(kq["theo_trang_thai"].items(), key=lambda kv: TRANG_THAI.index(kv[0]))), ""]
    # Khối gấp trước, mọi danh mục
    uu_tien = [m for dm in kq["danh_muc"].values() for m in dm["muc"] if m["trang_thai"] in ("gap", "cho-anh", "treo")]
    if uu_tien:
        L += ["## 🔥 Cần xử lý ngay (gấp · chờ anh · treo)"]
        L += [_dong(m) for m in sorted(uu_tien, key=lambda m: (TRANG_THAI.index(m["trang_thai"]), m["ts"]), reverse=False)]
        L.append("")
    for dm, d in kq["danh_muc"].items():
        tt = " · ".join(f"{NHAN[k].split(' ', 1)[0]}{v}" for k, v in d["theo_trang_thai"].items())
        L += [f"## {d['nhan']} ({d['so']}) {tt}"]
        for m in d["muc"]:
            if not chi_tiet and m["trang_thai"] == "xong":
                continue
            L.append(_dong(m))
            if m["tom_tat"] and m["trang_thai"] != "xong":
                L.append(f"  > {m['tom_tat'][:200].replace(chr(10), ' ')}")
        L.append("")
    return "\n".join(L) + "\n"


def khoi_chep_tat_ca(kq: dict[str, Any], *, ngay: str) -> str:
    """Bản gọn để chép đưa cho AI tổng hợp: chỉ việc còn mở, không tóm tắt dài, đã che."""
    L = [f"TỔNG HỢP VIỆC CÒN MỞ — {ngay} — {kq['con_mo']}/{kq['tong']} mục"]
    for dm, d in kq["danh_muc"].items():
        mo = [m for m in d["muc"] if m["trang_thai"] != "xong"]
        if not mo:
            continue
        L.append(f"\n[{d['nhan']}] {len(mo)} việc")
        L += [f"{NHAN[m['trang_thai']].split(' ', 1)[0]} {m['tieu_de']}" + (f" | {m['nguon']}" if m["nguon"] else "") for m in mo]
    return "\n".join(L) + "\n"


def cap_nhat_index(ra: Path) -> str:
    files = sorted(ra.glob("tong-hop-*.md"), reverse=True)
    files = [f for f in files if f.name != "tong-hop-index.md"]
    L = ["# Mục lục tổng hợp (mới → cũ)", ""]
    for f in files:
        try:
            first = f.read_text(encoding="utf-8").splitlines()
            dong3 = next((x for x in first if x.startswith("**")), "")
        except OSError:
            dong3 = ""
        L.append(f"- [{f.stem.replace('tong-hop-', '')}]({f.name}) {dong3}")
    text = "\n".join(L) + "\n"
    (ra / "tong-hop-index.md").write_text(text, encoding="utf-8")
    return text


def chay(nguon: list[Path], ra: Path, *, bay_gio: datetime | None = None, treo_gio: float = 6, tu_ngay: datetime | None = None) -> dict[str, Any]:
    bay_gio = bay_gio or datetime.now(VN)
    muc = noi_ket_qua(quet(nguon, tu_ngay=tu_ngay), bay_gio=bay_gio, treo_gio=treo_gio)
    kq = tong_ket(muc)
    ngay = bay_gio.strftime("%Y-%m-%d")
    ra.mkdir(parents=True, exist_ok=True)
    md = markdown(kq, ngay=ngay)
    chep = khoi_chep_tat_ca(kq, ngay=ngay)
    (ra / f"tong-hop-{ngay}.md").write_text(md + "\n---\n## 📋 CHÉP TẤT CẢ (bản gọn, đã che)\n```\n" + chep + "```\n", encoding="utf-8")
    (ra / f"tong-hop-{ngay}.json").write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")
    (ra / "chep-tat-ca.txt").write_text(chep, encoding="utf-8")
    cap_nhat_index(ra)
    kq["ngay"] = ngay
    return kq


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):  # console Windows cp1252
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nguon", action="append", required=True, help="thư mục quét (lặp lại được)")
    ap.add_argument("--ra", required=True)
    ap.add_argument("--treo-gio", type=float, default=6)
    ap.add_argument("--tu-ngay", help="chỉ lấy mục từ YYYY-MM-DD")
    args = ap.parse_args(argv)
    tu_ngay = datetime.strptime(args.tu_ngay, "%Y-%m-%d").replace(tzinfo=VN) if args.tu_ngay else None
    kq = chay([Path(n) for n in args.nguon], Path(args.ra), treo_gio=args.treo_gio, tu_ngay=tu_ngay)
    print(f"{kq['tong']} mục · còn mở {kq['con_mo']} · xong {kq['xong']} ({kq['ti_le_xong']}%) → {args.ra}/tong-hop-{kq['ngay']}.md")
    for dm, d in kq["danh_muc"].items():
        print(f"  {d['nhan']}: {d['so']} ({', '.join(f'{k} {v}' for k, v in d['theo_trang_thai'].items())})")
    return 0 if kq["tong"] else 1


if __name__ == "__main__":
    sys.exit(main())
