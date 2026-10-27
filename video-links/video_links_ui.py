"""Giao diện Tkinter: bảng link video YouTube/TikTok + Mở tệp trong thư mục + thanh % tiến độ.

Chạy riêng:  python video_links_ui.py so_video.json
Nhúng vào app .exe có sẵn:  VideoLinksPanel(khung_cha, videos)  rồi  tao_menu(root, panel)  (xem README).
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import video_links as vl  # noqa: E402

COLS = ("ma", "ten", "nen_tang", "trang_thai", "tien_do", "url", "tep")
HEADS = {"ma": "Mã", "ten": "Tên video", "nen_tang": "Nền tảng", "trang_thai": "Trạng thái",
         "tien_do": "%", "url": "Link", "tep": "Tệp"}
WIDTHS = {"ma": 60, "ten": 260, "nen_tang": 80, "trang_thai": 90, "tien_do": 50, "url": 300, "tep": 320}
ICON_THU_MUC = "📂"


class VideoLinksPanel(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        videos: list[vl.Video],
        *,
        folder_opener: Callable[[str], tuple[bool, str]] = vl.open_in_folder,
        link_opener: Callable[[str], tuple[bool, str]] = vl.open_link,
    ) -> None:
        super().__init__(master)
        self._folder_opener, self._link_opener = folder_opener, link_opener
        self._videos: list[vl.Video] = []
        self._by_iid: dict[str, vl.Video] = {}
        self.loc_nen_tang = tk.StringVar(value="tat-ca")
        self.status_var = tk.StringVar(value="Chọn một dòng rồi bấm 📂 Mở thư mục chứa tệp")
        self.summary_var = tk.StringVar()
        self.percent_var = tk.StringVar()

        # thanh công cụ có icon
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=(6, 2))
        self.btn_folder = ttk.Button(bar, text=f"{ICON_THU_MUC} Mở thư mục chứa tệp", command=self.mo_thu_muc)
        self.btn_folder.pack(side="left", padx=(0, 4))
        self.btn_link = ttk.Button(bar, text="🌐 Mở link", command=self.mo_link)
        self.btn_link.pack(side="left", padx=4)
        self.btn_copy = ttk.Button(bar, text="📋 Chép link", command=self.chep_link)
        self.btn_copy.pack(side="left", padx=4)
        ttk.Label(bar, text="Hiện:").pack(side="left", padx=(16, 2))
        for value, label in (("tat-ca", "Tất cả"), ("youtube", "YouTube"), ("tiktok", "TikTok")):
            ttk.Radiobutton(bar, text=label, value=value, variable=self.loc_nen_tang,
                            command=self.ve_lai).pack(side="left")
        ttk.Label(self, textvariable=self.summary_var).pack(fill="x", padx=8)

        # bảng
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree = ttk.Treeview(body, columns=COLS, show="headings", selectmode="browse", height=14)
        for c in COLS:
            self.tree.heading(c, text=HEADS[c])
            self.tree.column(c, width=WIDTHS[c], anchor="center" if c in ("ma", "tien_do", "nen_tang", "trang_thai") else "w")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self.mo_thu_muc())
        self.tree.bind("<Return>", lambda _e: self.mo_thu_muc())
        self.tree.bind("<Button-3>", self._menu_chuot_phai)

        self.context = tk.Menu(self, tearoff=0)
        self.context.add_command(label=f"{ICON_THU_MUC} Mở thư mục chứa tệp", command=self.mo_thu_muc)
        self.context.add_command(label="🌐 Mở link", command=self.mo_link)
        self.context.add_command(label="📋 Chép link", command=self.chep_link)

        # thanh % tiến độ chung
        foot = ttk.Frame(self)
        foot.pack(fill="x", padx=6, pady=(0, 6))
        self.progress = ttk.Progressbar(foot, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(foot, textvariable=self.percent_var, width=26).pack(side="left", padx=6)
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x", padx=8, pady=(0, 6))

        self.cap_nhat(videos)

    # ---- dữ liệu
    def cap_nhat(self, videos: list[vl.Video]) -> None:
        self._videos = list(videos)
        self.ve_lai()

    def _hien(self) -> list[vl.Video]:
        nen = self.loc_nen_tang.get()
        return [v for v in self._videos if nen == "tat-ca" or v.nen_tang == nen]

    def ve_lai(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._by_iid = {}
        shown = self._hien()
        for i, v in enumerate(shown):
            iid = f"v{i}"
            self._by_iid[iid] = v
            self.tree.insert("", "end", iid=iid, values=(
                v.ma, v.ten, v.nhan_nen_tang, v.nhan_trang_thai, f"{v.tien_do}%", v.url or "(chưa có link)", v.tep or "(chưa có tệp)"))
        s = vl.tong_ket(shown)
        self.progress["value"] = s["ti_le_da_dang"]
        self.percent_var.set(f"{s['ti_le_da_dang']}% · đã đăng {s['da_dang']}/{s['tong']}")
        parts = [f"{vl.NEN_TANG.get(n, n)} {d['da_dang']}/{d['tong']}" for n, d in sorted(s["theo_nen_tang"].items())]
        self.summary_var.set(" · ".join(parts) if parts else "Chưa có video")

    # ---- thao tác
    def chon(self) -> vl.Video | None:
        sel = self.tree.selection()
        return self._by_iid.get(sel[0]) if sel else None

    def mo_thu_muc(self) -> None:
        v = self.chon()
        if v is None:
            self.status_var.set("Chọn một dòng trước")
            return
        if not v.tep:
            self.status_var.set(f"{v.ma}: video này chưa có đường dẫn tệp")
            return
        ok, msg = self._folder_opener(v.tep)
        self.status_var.set(f"{v.ma}: {msg}" if ok else f"{v.ma}: LỖI — {msg}")

    def mo_link(self) -> None:
        v = self.chon()
        if v is None:
            self.status_var.set("Chọn một dòng trước")
            return
        ok, msg = self._link_opener(v.url)
        self.status_var.set(f"{v.ma}: {msg}" if ok else f"{v.ma}: {msg}")

    def chep_link(self) -> None:
        v = self.chon()
        if v is None or not v.url:
            self.status_var.set("Chọn một dòng có link trước")
            return
        self.clipboard_clear()
        self.clipboard_append(v.url)
        self.status_var.set(f"{v.ma}: đã chép link")

    def _menu_chuot_phai(self, event: Any) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.context.tk_popup(event.x_root, event.y_root)


def tao_menu(root: tk.Tk, panel: VideoLinksPanel) -> tk.Menu:
    """Thanh menu có mục Mở tệp trong thư mục (Ctrl+O)."""
    menubar = tk.Menu(root, tearoff=0)  # tearoff=0: không có mục 'tách rời' chiếm vị trí 0
    tep = tk.Menu(menubar, tearoff=0)
    tep.add_command(label=f"{ICON_THU_MUC} Mở tệp trong thư mục\tCtrl+O", command=panel.mo_thu_muc)
    tep.add_command(label="🌐 Mở link\tCtrl+L", command=panel.mo_link)
    tep.add_command(label="📋 Chép link\tCtrl+C", command=panel.chep_link)
    tep.add_separator()
    tep.add_command(label="Thoát", command=root.destroy)
    menubar.add_cascade(label="Tệp", menu=tep)
    xem = tk.Menu(menubar, tearoff=0)
    for value, label in (("tat-ca", "Tất cả"), ("youtube", "YouTube"), ("tiktok", "TikTok")):
        xem.add_radiobutton(label=label, value=value, variable=panel.loc_nen_tang, command=panel.ve_lai)
    menubar.add_cascade(label="Xem", menu=xem)
    root.config(menu=menubar)
    root.bind("<Control-o>", lambda _e: panel.mo_thu_muc())
    root.bind("<Control-l>", lambda _e: panel.mo_link())
    return menubar


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Dùng: python video_links_ui.py <so_video.json|csv>")
        return 1
    root = tk.Tk()
    root.title("Link video YouTube · TikTok — DienmayVIP")
    root.geometry("1100x520")
    panel = VideoLinksPanel(root, vl.load_videos(Path(args[0])))
    panel.pack(fill="both", expand=True)
    tao_menu(root, panel)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
