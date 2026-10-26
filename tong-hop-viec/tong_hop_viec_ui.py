"""Giao diện Tkinter kiểu Lark Mail: danh mục bên trái, nội dung bên phải, nút 📋 Chép tất cả / Chép mục này, thanh % xong.

  python tong_hop_viec_ui.py --nguon <thư mục> [--nguon ...] --ra <thư mục kết quả>
"""
from __future__ import annotations

import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tong_hop_viec as th  # noqa: E402


class TongHopPanel(ttk.Frame):
    def __init__(self, master: tk.Misc, kq: dict[str, Any]) -> None:
        super().__init__(master)
        self.kq = kq
        self.status_var = tk.StringVar(value="Chọn danh mục bên trái. 📋 Chép tất cả = bản gọn mọi việc còn mở, đã che số nhạy cảm.")
        self.percent_var = tk.StringVar()
        self.chi_mo = tk.BooleanVar(value=True)

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=(6, 2))
        self.btn_all = ttk.Button(bar, text="📋 Chép tất cả", command=self.chep_tat_ca)
        self.btn_all.pack(side="left")
        self.btn_one = ttk.Button(bar, text="📋 Chép mục này", command=self.chep_muc)
        self.btn_one.pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="Chỉ việc còn mở", variable=self.chi_mo, command=self.ve_lai).pack(side="left", padx=12)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=6, pady=4)
        self.list = tk.Listbox(body, width=34, exportselection=False)
        body.add(self.list, weight=0)
        self.text = tk.Text(body, wrap="word", font=("Segoe UI", 10))
        body.add(self.text, weight=1)
        self.list.bind("<<ListboxSelect>>", lambda _e: self.ve_lai())

        foot = ttk.Frame(self)
        foot.pack(fill="x", padx=6, pady=(0, 6))
        self.progress = ttk.Progressbar(foot, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(foot, textvariable=self.percent_var, width=28).pack(side="left", padx=6)
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x", padx=8, pady=(0, 6))
        self.cap_nhat(kq)

    def cap_nhat(self, kq: dict[str, Any]) -> None:
        self.kq = kq
        self.keys = ["__tat_ca__"] + list(kq["danh_muc"])
        self.list.delete(0, "end")
        self.list.insert("end", f"🔥 Tất cả · còn mở {kq['con_mo']}")
        for dm in kq["danh_muc"].values():
            mo = sum(v for k, v in dm["theo_trang_thai"].items() if k != "xong")
            self.list.insert("end", f"{dm['nhan']} · {mo}/{dm['so']}")
        self.list.selection_set(0)
        self.progress["value"] = kq["ti_le_xong"]
        self.percent_var.set(f"{kq['ti_le_xong']}% xong · còn mở {kq['con_mo']}/{kq['tong']}")
        self.ve_lai()

    def _chon(self) -> str:
        sel = self.list.curselection()
        return self.keys[sel[0]] if sel else "__tat_ca__"

    def noi_dung_muc(self, key: str) -> str:
        chi_mo = self.chi_mo.get()
        dms = self.kq["danh_muc"] if key == "__tat_ca__" else {key: self.kq["danh_muc"][key]}
        L = []
        for d in dms.values():
            items = [m for m in d["muc"] if not (chi_mo and m["trang_thai"] == "xong")]
            if not items:
                continue
            L.append(f"== {d['nhan']} ({len(items)}) ==")
            for m in items:
                L.append(th._dong(m))
                if m["tom_tat"] and m["trang_thai"] != "xong":
                    L.append("   " + m["tom_tat"][:200].replace("\n", " "))
            L.append("")
        return "\n".join(L) if L else "(không có việc nào)"

    def ve_lai(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.noi_dung_muc(self._chon()))
        self.text.configure(state="disabled")

    def chep_tat_ca(self) -> None:
        chep = th.khoi_chep_tat_ca(self.kq, ngay=self.kq.get("ngay", ""))
        self.clipboard_clear()
        self.clipboard_append(chep)
        self.status_var.set(f"Đã chép {chep.count(chr(10))} dòng (mọi việc còn mở, đã che)")

    def chep_muc(self) -> None:
        text = self.noi_dung_muc(self._chon())
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(f"Đã chép {text.count(chr(10)) + 1} dòng của mục đang xem")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--nguon", action="append", required=True)
    ap.add_argument("--ra", required=True)
    ap.add_argument("--treo-gio", type=float, default=6)
    args = ap.parse_args(argv)
    kq = th.chay([Path(n) for n in args.nguon], Path(args.ra), treo_gio=args.treo_gio)
    root = tk.Tk()
    root.title(f"Tổng hợp việc — {datetime.now(th.VN):%d/%m/%Y %H:%M}")
    root.geometry("1100x640")
    TongHopPanel(root, kq).pack(fill="both", expand=True)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
