"""Kiểm chuẩn Harness² cho MỌI app (thư mục mã). 0 token. Chỉ đọc, không sửa app.

  python kiem_chuan_app.py --goc "C:\\Service" --goc "C:\\ClaudeVIP" --ra ket-qua [--bat-buoc kiem,help]

Mỗi thư mục con có tệp .py là một app. Kiểm:
  kiem       có lệnh --kiem (tự kiểm)                 bat-buoc
  help       có HELP.md (F1)                          bat-buoc
  kien-thuc  có KIEN-THUC-APP.md                      khuyến nghị
  log        có ghi log ra tệp (.log / logging)       khuyến nghị
  trang-thai có ghi trạng thái (trang-thai*.json)     khuyến nghị
  bak        có bản .bak-* (thói quen sao lưu)        khuyến nghị
  bi-mat     KHÔNG có khóa/mật khẩu gán cứng          bat-buoc (hỏng = đỏ)
  loi-cu     loi.log cũ hơn mã → lỗi đã sửa, bỏ qua   thông tin (luật 26/10: so mtime lỗi vs mã)
Ghi chuan-app.json + chuan-app.md. Mã thoát 1 nếu có app hỏng mục bắt buộc.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

BO_QUA = {"venv", ".venv", "site-packages", "node_modules", ".git", "__pycache__", "_shared", "tests", "test", "dist", "build"}
MAU_BI_MAT = re.compile(
    r"AIza[0-9A-Za-z_\-]{35}|\bsk-[A-Za-z0-9_\-]{20,}|\bgh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?:api[_\-]?key|secret|passw(?:or)?d|token|m[aậ]t[_\- ]?kh[aẩ]u)[\"']?\s*[:=]\s*[\"'][^\"'\n]{8,}[\"']", re.IGNORECASE)
MAU_BI_MAT_LANH = re.compile(r"os\.(environ|getenv)|getenv\(|<|\{|%|\$|input\(|example|mẫu|placeholder|your[_\-]", re.IGNORECASE)
MAC_DINH_BAT_BUOC = ("kiem", "help", "bi-mat")


@dataclass
class App:
    ten: str
    duong_dan: str
    so_py: int
    ket_qua: dict[str, bool] = field(default_factory=dict)
    ghi_chu: list[str] = field(default_factory=list)
    hong_bat_buoc: list[str] = field(default_factory=list)


def _doc(p: Path, max_bytes: int = 2_000_000) -> str:
    try:
        if p.stat().st_size > max_bytes:
            return ""
        return p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def co_bi_mat_gan_cung(text: str) -> bool:
    for m in MAU_BI_MAT.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        line = text[line_start:text.find("\n", m.end()) if text.find("\n", m.end()) != -1 else len(text)]
        if MAU_BI_MAT_LANH.search(line):
            continue
        return True
    return False


def kiem_app(thu_muc: Path, *, bat_buoc: Iterable[str] = MAC_DINH_BAT_BUOC) -> App:
    py = [p for p in thu_muc.rglob("*.py") if not any(part.lower() in BO_QUA for part in p.relative_to(thu_muc).parts)]
    app = App(ten=thu_muc.name, duong_dan=str(thu_muc), so_py=len(py))
    texts = {p: _doc(p) for p in py}
    all_text = "\n".join(texts.values())
    ten_tep = {p.name.lower() for p in thu_muc.iterdir() if p.is_file()} if thu_muc.is_dir() else set()
    kq = app.ket_qua
    kq["kiem"] = "--kiem" in all_text
    kq["help"] = "help.md" in ten_tep
    kq["kien-thuc"] = "kien-thuc-app.md" in ten_tep
    kq["log"] = bool(re.search(r"\.log\b|logging\.|RotatingFileHandler", all_text))
    kq["trang-thai"] = bool(re.search(r"trang[-_]thai[^\n]*\.json", all_text, re.IGNORECASE))
    kq["bak"] = any(".bak" in n for n in ten_tep)
    kq["bi-mat"] = not any(co_bi_mat_gan_cung(t) for t in texts.values())
    # lỗi cũ hơn mã → đã sửa rồi
    loi = thu_muc / "loi.log"
    if loi.is_file() and py:
        mtime_ma = max(p.stat().st_mtime for p in py)
        if loi.stat().st_mtime < mtime_ma:
            app.ghi_chu.append("loi.log cũ hơn lần sửa mã cuối → lỗi đã sửa, không vá lại")
    for k in bat_buoc:
        if not kq.get(k, False):
            app.hong_bat_buoc.append(k)
    return app


def tim_app(goc: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for g in goc:
        g = Path(g)
        if not g.is_dir():
            continue
        for d in sorted(g.iterdir()):
            if d.is_dir() and d.name.lower() not in BO_QUA and not d.name.startswith((".", "_")) and any(d.rglob("*.py")):
                out.append(d)
    return out


def markdown(apps: list[App]) -> str:
    cols = ["kiem", "help", "kien-thuc", "log", "trang-thai", "bak", "bi-mat"]
    L = ["# Chuẩn Harness² cho app", "", f"{len(apps)} app · hỏng bắt buộc: {sum(bool(a.hong_bat_buoc) for a in apps)}", "",
         "| App | " + " | ".join(cols) + " | Ghi chú |", "|---|" + "---|" * (len(cols) + 1)]
    for a in sorted(apps, key=lambda a: (not a.hong_bat_buoc, a.ten)):
        cells = " | ".join("✅" if a.ket_qua.get(c) else ("❌" if c in a.hong_bat_buoc else "–") for c in cols)
        L.append(f"| {a.ten} | {cells} | {'; '.join(a.ghi_chu)} |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goc", action="append", required=True)
    ap.add_argument("--ra", required=True)
    ap.add_argument("--bat-buoc", default=",".join(MAC_DINH_BAT_BUOC))
    args = ap.parse_args(argv)
    bat_buoc = [x.strip() for x in args.bat_buoc.split(",") if x.strip()]
    apps = [kiem_app(d, bat_buoc=bat_buoc) for d in tim_app([Path(g) for g in args.goc])]
    ra = Path(args.ra)
    ra.mkdir(parents=True, exist_ok=True)
    (ra / "chuan-app.json").write_text(json.dumps([asdict(a) for a in apps], ensure_ascii=False, indent=2), encoding="utf-8")
    (ra / "chuan-app.md").write_text(markdown(apps), encoding="utf-8")
    print(markdown(apps))
    return 1 if any(a.hong_bat_buoc for a in apps) else 0


if __name__ == "__main__":
    sys.exit(main())
