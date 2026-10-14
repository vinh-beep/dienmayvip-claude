"""VietQR Phiếu Thu — DienmayVIP.
Tạo QR chuyển khoản offline từ phiếu bán (SQL HTsoft, chỉ đọc) hoặc nhập tay.

Trái: danh sách phiếu bán (tìm theo số phiếu / tên khách).
Giữa: ngân hàng nhận, khách, sản phẩm, số tiền, nội dung CK (tự ghép, sửa được).
Phải: QR xem trước + Lưu PNG / Chép ảnh / In / Mở thư mục.
"""
import csv
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import ImageTk

from phieu_ban_sql import NguonSQL, doc_cau_hinh
from vietqr_core import GHI_CHU_TOI_DA, MAU_NOI_DUNG, noi_dung_ck, payload, ve_qr

if getattr(sys, "frozen", False):  # chạy từ .exe (PyInstaller)
    HERE = pathlib.Path(sys.executable).parent
else:
    HERE = pathlib.Path(__file__).parent
THU_MUC_QR = HERE / "out" / "don-hang"
CAU_HINH = HERE / "phieu_ban.config.json"


def doc_tai_khoan():
    return json.loads((HERE / "accounts.json").read_text(encoding="utf-8"))


def dinh_dang_tien(v):
    try:
        return f"{int(float(v)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def so_tien_tu_chuoi(s):
    s = "".join(ch for ch in str(s) if ch.isdigit())
    return int(s) if s else 0


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VietQR Phiếu Thu — DienmayVIP")
        self.geometry("1280x720")
        self.minsize(960, 560)
        self.tai_khoan = doc_tai_khoan()
        cfg, self.trang_thai_sql = doc_cau_hinh(CAU_HINH)
        self.nguon = NguonSQL(cfg) if cfg else None
        self.mau = (cfg or {}).get("mau_noi_dung", MAU_NOI_DUNG)
        self.phieu = []
        self._anh = None
        self._hen = None
        self._dung_ui()
        if self.nguon:
            self.tai_phieu()
        self.cap_nhat()

    # ---------- giao diện ----------
    def _dung_ui(self):
        style = ttk.Style(self)
        style.configure("Tieu.TLabel", font=("Segoe UI", 11, "bold"))
        khung = self.khung = ttk.PanedWindow(self, orient="horizontal")
        khung.pack(fill="both", expand=True, padx=6, pady=6)

        trai = ttk.Frame(khung, padding=6)
        ttk.Label(trai, text="Phiếu bán", style="Tieu.TLabel").pack(anchor="w")
        tim = ttk.Frame(trai)
        tim.pack(fill="x", pady=4)
        self.v_tim = tk.StringVar()
        o_tim = ttk.Entry(tim, textvariable=self.v_tim)
        o_tim.pack(side="left", fill="x", expand=True)
        o_tim.bind("<Return>", lambda e: self.tai_phieu())
        ttk.Button(tim, text="Tìm", command=self.tai_phieu).pack(side="left", padx=(4, 0))
        cot = ("so", "ngay", "khach", "tong")
        self.bang = ttk.Treeview(trai, columns=cot, show="headings", selectmode="browse")
        for c, t, w in zip(cot, ("Số phiếu", "Ngày", "Khách", "Tổng"), (78, 78, 125, 92)):
            self.bang.heading(c, text=t)
            self.bang.column(c, width=w, anchor="e" if c == "tong" else "w")
        cuon = ttk.Scrollbar(trai, orient="vertical", command=self.bang.yview)
        self.bang.configure(yscrollcommand=cuon.set)
        cuon.pack(side="right", fill="y")
        self.bang.pack(fill="both", expand=True)
        self.bang.bind("<<TreeviewSelect>>", self.chon_phieu)
        self.nhan_sql = ttk.Label(trai, text=self.trang_thai_sql, wraplength=380, foreground="#666")
        self.nhan_sql.pack(anchor="w", pady=(4, 0))
        khung.add(trai, weight=3)

        giua = ttk.Frame(khung, padding=10)
        ttk.Label(giua, text="Thông tin thanh toán", style="Tieu.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.v_nh = tk.StringVar(value=f"{self.tai_khoan[0]['bank']} — {self.tai_khoan[0]['stk']}")
        self.v_so = tk.StringVar()
        self.v_khach = tk.StringVar()
        self.v_sp = tk.StringVar()
        self.v_tien = tk.StringVar()
        self.v_tu_ghep = tk.BooleanVar(value=True)
        hang = [
            ("Ngân hàng nhận", ttk.Combobox(giua, textvariable=self.v_nh, state="readonly",
                                             values=[f"{a['bank']} — {a['stk']}" for a in self.tai_khoan])),
            ("Số phiếu", ttk.Entry(giua, textvariable=self.v_so)),
            ("Khách hàng", ttk.Entry(giua, textvariable=self.v_khach)),
            ("Sản phẩm", ttk.Entry(giua, textvariable=self.v_sp)),
            ("Số tiền (đ)", ttk.Entry(giua, textvariable=self.v_tien, font=("Segoe UI", 12, "bold"))),
        ]
        for i, (nhan, o) in enumerate(hang, start=1):
            ttk.Label(giua, text=nhan).grid(row=i, column=0, sticky="w", pady=3)
            o.grid(row=i, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(giua, text="Tự ghép nội dung CK", variable=self.v_tu_ghep,
                        command=self.cap_nhat).grid(row=6, column=1, sticky="w", pady=(8, 0))
        ttk.Label(giua, text="Nội dung CK").grid(row=7, column=0, sticky="nw", pady=3)
        self.o_nd = tk.Text(giua, height=4, wrap="word", font=("Segoe UI", 10))
        self.o_nd.grid(row=7, column=1, sticky="ew", pady=3)
        self.nhan_dem = ttk.Label(giua, text="", foreground="#666")
        self.nhan_dem.grid(row=8, column=1, sticky="e")
        ttk.Button(giua, text="Xóa trắng (nhập tay)", command=self.xoa_trang).grid(
            row=9, column=1, sticky="w", pady=(12, 0))
        giua.columnconfigure(1, weight=1)
        khung.add(giua, weight=3)

        phai = ttk.Frame(khung, padding=6)
        ttk.Label(phai, text="Mã QR", style="Tieu.TLabel").pack(anchor="w")
        self.o_anh = ttk.Label(phai, anchor="center")
        self.o_anh.pack(fill="both", expand=True, pady=4)
        nut = ttk.Frame(phai)
        nut.pack(fill="x")
        for i, (t, f) in enumerate((("Lưu PNG", self.luu), ("Chép ảnh", self.chep_anh),
                                    ("In", self.in_qr), ("Mở thư mục", self.mo_thu_muc))):
            ttk.Button(nut, text=t, command=f).grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
        nut.columnconfigure((0, 1), weight=1)
        khung.add(phai, weight=3)

        for v in (self.v_nh, self.v_so, self.v_khach, self.v_sp, self.v_tien):
            v.trace_add("write", lambda *a: self.hen_cap_nhat())
        self.o_nd.bind("<KeyRelease>", lambda e: self._nd_sua_tay())
        self.o_anh.bind("<Configure>", lambda e: self.hen_cap_nhat())
        self.after(300, lambda: (khung.sashpos(0, 400), khung.sashpos(1, 790)))

    # ---------- dữ liệu ----------
    def tai_phieu(self):
        if not self.nguon:
            return
        self.nhan_sql.config(text="Đang tải phiếu…")
        tu_khoa = self.v_tim.get().strip()

        def chay():
            try:
                rows = self.nguon.danh_sach(tu_khoa)
                self.after(0, self._hien_phieu, rows, None)
            except Exception as e:  # lỗi kết nối: báo, không làm sập app
                self.after(0, self._hien_phieu, [], e)

        threading.Thread(target=chay, daemon=True).start()

    def _hien_phieu(self, rows, loi):
        self.phieu = rows
        self.bang.delete(*self.bang.get_children())
        for i, r in enumerate(rows):
            ngay = r["NGAY"].strftime("%d/%m/%Y") if hasattr(r["NGAY"], "strftime") else str(r["NGAY"])
            self.bang.insert("", "end", iid=str(i), values=(
                r["SOPHIEU"], ngay, r["KHACH"] or "", dinh_dang_tien(r["TONG"])))
        if loi:
            self.nhan_sql.config(text=f"Không đọc được SQL ({type(loi).__name__}). Vẫn nhập tay được.")
        else:
            self.nhan_sql.config(text=f"{len(rows)} phiếu trong {self.nguon.cfg['so_ngay']} ngày gần nhất")

    def chon_phieu(self, _e=None):
        sel = self.bang.selection()
        if not sel:
            return
        r = self.phieu[int(sel[0])]
        self.v_so.set(r["SOPHIEU"] or "")
        self.v_khach.set(r["KHACH"] or "")
        self.v_tien.set(dinh_dang_tien(r["TONG"]))
        self.v_sp.set("…")
        self.v_tu_ghep.set(True)

        def chay():
            try:
                sp = self.nguon.san_pham(r["ID"])
            except Exception:
                sp = ""
            self.after(0, self.v_sp.set, sp)

        threading.Thread(target=chay, daemon=True).start()

    def xoa_trang(self):
        self.bang.selection_remove(self.bang.selection())
        for v in (self.v_so, self.v_khach, self.v_sp, self.v_tien):
            v.set("")
        self.v_tu_ghep.set(True)
        self.cap_nhat()

    # ---------- QR ----------
    def _tk_dang_chon(self):
        nh = self.v_nh.get()
        return next(a for a in self.tai_khoan if f"{a['bank']} — {a['stk']}" == nh)

    def _nd_sua_tay(self):
        self.v_tu_ghep.set(False)
        self.hen_cap_nhat()

    def hen_cap_nhat(self):
        if self._hen:
            self.after_cancel(self._hen)
        self._hen = self.after(250, self.cap_nhat)

    def _du_lieu(self):
        tien = so_tien_tu_chuoi(self.v_tien.get())
        if self.v_tu_ghep.get():
            nd = noi_dung_ck(self.v_khach.get(), self.v_sp.get(), tien, self.mau) \
                if self.v_khach.get().strip() else ""
            self.o_nd.delete("1.0", "end")
            self.o_nd.insert("1.0", nd)
        else:
            nd = self.o_nd.get("1.0", "end").strip()
        return self._tk_dang_chon(), tien, nd

    def cap_nhat(self):
        self._hen = None
        tk_, tien, nd = self._du_lieu()
        dai = len(nd)
        self.nhan_dem.config(text=f"{dai}/{GHI_CHU_TOI_DA} ký tự" + (" — sẽ bị cắt" if dai > GHI_CHU_TOI_DA else ""),
                             foreground="#c00" if dai > GHI_CHU_TOI_DA else "#666")
        try:
            anh = ve_qr(tk_, tien or None, nd or None)
        except ValueError as e:
            self.o_anh.config(image="", text=str(e))
            return
        self._anh_goc = anh
        rong = max(self.o_anh.winfo_width(), 200)
        cao = max(self.o_anh.winfo_height(), 300)
        ti_le = min(1.0, rong / anh.width, cao / anh.height)
        xem = anh.resize((int(anh.width * ti_le), int(anh.height * ti_le)))
        self._anh = ImageTk.PhotoImage(xem)
        self.o_anh.config(image=self._anh, text="")

    def luu(self, im_lang=False):
        tk_, tien, nd = self._du_lieu()
        THU_MUC_QR.mkdir(parents=True, exist_ok=True)
        so = self.v_so.get().strip() or "nhap-tay"
        so_an_toan = "".join(c if c.isalnum() or c in "-_" else "-" for c in so)
        f = THU_MUC_QR / f"QR {so_an_toan} {tk_['code']} {time.strftime('%d %m %Y %Hh%Mp')}.png"
        ve_qr(tk_, tien or None, nd or None).save(f)
        nk = THU_MUC_QR / "nhat-ky.csv"
        moi = not nk.exists()
        with nk.open("a", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            if moi:
                w.writerow(["Thoi gian", "So phieu", "Ngan hang", "STK", "So tien", "Noi dung", "Payload", "File"])
            w.writerow([time.strftime("%d/%m/%Y %H:%M"), so, tk_["bank"], tk_["stk"], tien, nd,
                        payload(tk_["bin"], tk_["stk"], tien or None, nd or None), f.name])
        if not im_lang:
            messagebox.showinfo("Đã lưu", f"Đã lưu:\n{f}")
        return f

    def chep_anh(self):
        f = self.luu(im_lang=True)
        if os.name != "nt":
            messagebox.showinfo("Chép ảnh", f"Chỉ hỗ trợ trên Windows. File: {f}")
            return
        ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
              f"[Windows.Forms.Clipboard]::SetImage([Drawing.Image]::FromFile('{f}'))")
        subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        messagebox.showinfo("Chép ảnh", "Đã chép QR. Dán (Ctrl+V) vào Zalo/Messenger.")

    def in_qr(self):
        f = self.luu(im_lang=True)
        if os.name == "nt":
            os.startfile(str(f), "print")
        else:
            messagebox.showinfo("In", f"Mở file để in: {f}")

    def mo_thu_muc(self):
        THU_MUC_QR.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(THU_MUC_QR))
        else:
            messagebox.showinfo("Thư mục", str(THU_MUC_QR))


if __name__ == "__main__":
    if "--tu-kiem" in sys.argv:  # chạy thử không mở cửa sổ lâu: dựng app, vẽ 1 QR, thoát
        app = App()
        app.v_khach.set("Khach Thu")
        app.v_sp.set("San pham thu")
        app.v_tien.set("1000")
        app.update()
        app.cap_nhat()
        ok = app._anh is not None
        print("TU KIEM OK" if ok else "TU KIEM LOI")
        app.destroy()
        sys.exit(0 if ok else 1)
    else:
        App().mainloop()
