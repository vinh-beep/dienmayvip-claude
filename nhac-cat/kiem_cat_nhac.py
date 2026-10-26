"""Kiểm kế hoạch cắt nhạc cho video (mỗi SP 1 bài): đoạn mở 0–3 s + cao trào dài tong_giay − 0.15, phải nằm trong bài.
Đọc lại ĐÍCH: độ dài thật của tệp nhạc (ffprobe nếu có, WAV đọc header), không tin số trong kế hoạch. 0 token.

  python kiem_cat_nhac.py --ke-hoach gan-nhac.json --ra ket-qua [--goc-ban-quyen "D:\\MP3"]

Kế hoạch: [{"sku": "A04", "tep": "D:\\MP3\\suno-a04.mp3", "doan_mo_giay": 2.5, "nhac_tu": 31.0, "tong_giay": 18.0}]
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

DOAN_MO_MAX = 3.0
TINH_CUOI = 0.15
VIDEO_MIN, VIDEO_MAX = 15.0, 20.0  # luật video 26/10: 15–20 s
DUOI_NHAC = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


def do_dai_wav(path: Path) -> float | None:
    try:
        with open(path, "rb") as f:
            head = f.read(12)
            if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                return None
            byte_rate = None
            while True:
                chunk = f.read(8)
                if len(chunk) < 8:
                    return None
                cid, size = chunk[:4], struct.unpack("<I", chunk[4:])[0]
                if cid == b"fmt ":
                    fmt = f.read(size)
                    byte_rate = struct.unpack("<I", fmt[8:12])[0]
                elif cid == b"data":
                    return size / byte_rate if byte_rate else None
                else:
                    f.seek(size + (size & 1), 1)
    except (OSError, struct.error):
        return None


def do_dai_ffprobe(path: Path, runner: Callable[..., Any] = subprocess.run) -> float | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        p = runner([exe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                   capture_output=True, encoding="utf-8", errors="replace", timeout=60)
        return float(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def do_dai(path: Path, *, ffprobe: Callable[[Path], float | None] = do_dai_ffprobe) -> float | None:
    if not path.is_file():
        return None
    if path.suffix.lower() == ".wav":
        d = do_dai_wav(path)
        if d is not None:
            return d
    return ffprobe(path)


def ban_quyen_ro(path: Path, goc_ban_quyen: list[Path]) -> bool:
    low = str(path).lower()
    if "suno" in low:
        return True
    return any(str(path).lower().startswith(str(g).lower().rstrip("\\/")) for g in goc_ban_quyen)


def kiem_mot(muc: dict[str, Any], *, goc_ban_quyen: list[Path], do_dai_fn: Callable[[Path], float | None] = do_dai) -> dict[str, Any]:
    sku = str(muc.get("sku") or "")
    tep = Path(str(muc.get("tep") or ""))
    loi: list[str] = []
    try:
        doan_mo = float(muc.get("doan_mo_giay", 0) or 0)
        nhac_tu = float(muc.get("nhac_tu", 0) or 0)
        tong = float(muc.get("tong_giay", 0) or 0)
    except (TypeError, ValueError):
        return {"sku": sku, "dat": False, "loi": ["số giây không hợp lệ"]}
    if not sku:
        loi.append("thiếu sku")
    if tep.suffix.lower() not in DUOI_NHAC:
        loi.append(f"đuôi tệp không phải nhạc: {tep.suffix or '(trống)'}")
    if not 0 <= doan_mo <= DOAN_MO_MAX:
        loi.append(f"đoạn mở {doan_mo} s ngoài 0–{DOAN_MO_MAX} s")
    if not VIDEO_MIN <= tong <= VIDEO_MAX:
        loi.append(f"video {tong} s ngoài {VIDEO_MIN:.0f}–{VIDEO_MAX:.0f} s (luật 26/10)")
    if nhac_tu < 0:
        loi.append("nhac_tu âm")
    cao_trao = max(tong - TINH_CUOI, 0)
    can = nhac_tu + cao_trao
    dai = do_dai_fn(tep) if tep.suffix.lower() in DUOI_NHAC else None
    if dai is None:
        loi.append("không đọc được độ dài tệp nhạc (thiếu tệp hoặc không có ffprobe)")
    elif can > dai + 0.01:
        loi.append(f"cắt {nhac_tu:.2f}→{can:.2f} s vượt độ dài bài {dai:.2f} s")
    bq = ban_quyen_ro(tep, goc_ban_quyen)
    if not bq:
        loi.append("chưa rõ bản quyền thương mại (không nằm trong thư mục nhạc có phép, không phải Suno)")
    return {"sku": sku, "tep": str(tep), "do_dai_bai": dai, "doan_mo_giay": doan_mo, "nhac_tu": nhac_tu,
            "nhac_den": round(can, 2), "cao_trao_giay": round(cao_trao, 2), "ban_quyen_ro": bq, "dat": not loi, "loi": loi}


def kiem(ke_hoach: list[dict[str, Any]], *, goc_ban_quyen: list[Path], do_dai_fn=do_dai) -> dict[str, Any]:
    muc = [kiem_mot(m, goc_ban_quyen=goc_ban_quyen, do_dai_fn=do_dai_fn) for m in ke_hoach]
    seen: dict[str, list[str]] = {}
    for m in muc:
        seen.setdefault(m.get("tep", ""), []).append(m["sku"])
    for m in muc:
        if len(seen.get(m.get("tep", ""), [])) > 1:
            m["dat"] = False
            m["loi"].append("bài này dùng cho nhiều SP: " + ", ".join(seen[m["tep"]]) + " (luật: mỗi SP 1 bài riêng)")
    return {"tong": len(muc), "dat": sum(m["dat"] for m in muc), "hong": sum(not m["dat"] for m in muc), "muc": muc}


def markdown(kq: dict[str, Any]) -> str:
    L = [f"# Kiểm cắt nhạc — đạt {kq['dat']}/{kq['tong']}", "", "| SKU | Bài (s) | Mở | Từ → đến | Bản quyền | Kết quả |", "|---|---:|---:|---|---|---|"]
    for m in kq["muc"]:
        dai = f"{m['do_dai_bai']:.1f}" if m.get("do_dai_bai") else "?"
        L.append(f"| {m['sku']} | {dai} | {m.get('doan_mo_giay', '')} | {m.get('nhac_tu', '')} → {m.get('nhac_den', '')} | "
                 f"{'rõ' if m.get('ban_quyen_ro') else 'CHƯA RÕ'} | {'ĐẠT' if m['dat'] else 'HỎNG: ' + '; '.join(m['loi'])} |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ke-hoach", required=True)
    ap.add_argument("--ra", required=True)
    ap.add_argument("--goc-ban-quyen", action="append", default=[], help="thư mục nhạc có phép thương mại (ví dụ D:\\MP3)")
    args = ap.parse_args(argv)
    try:
        data = json.loads(Path(args.ke_hoach).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(f"LỖI đọc kế hoạch: {exc}", file=sys.stderr)
        return 1
    kq = kiem(data if isinstance(data, list) else data.get("muc", []), goc_ban_quyen=[Path(g) for g in args.goc_ban_quyen])
    ra = Path(args.ra)
    ra.mkdir(parents=True, exist_ok=True)
    (ra / "kiem-cat-nhac.json").write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")
    (ra / "kiem-cat-nhac.md").write_text(markdown(kq), encoding="utf-8")
    print(markdown(kq))
    return 0 if kq["hong"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
