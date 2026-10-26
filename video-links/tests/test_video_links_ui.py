import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tk = pytest.importorskip("tkinter")

import video_links as vl  # noqa: E402

EXAMPLE = Path(__file__).resolve().parent.parent / "so_video.example.json"


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:  # máy không có màn hình (CI Linux)
        pytest.skip("không có màn hình để dựng Tk")
    r.withdraw()
    yield r
    r.destroy()


def make_panel(root, **kw):
    import video_links_ui as ui
    return ui.VideoLinksPanel(root, vl.load_videos(EXAMPLE), **kw)


def test_thanh_phan_tien_do_va_tong_ket(root):
    p = make_panel(root)
    assert float(p.progress["value"]) == 40
    assert p.percent_var.get() == "40% · đã đăng 2/5"
    assert "YouTube 1/2" in p.summary_var.get() and "TikTok 1/3" in p.summary_var.get()
    assert len(p.tree.get_children()) == 5


def test_chon_dong_roi_mo_thu_muc(root):
    calls = []
    p = make_panel(root, folder_opener=lambda path: (calls.append(path) or True, "Đã mở thư mục và chọn sẵn tệp"))
    p.tree.selection_set("v0")
    p.mo_thu_muc()
    assert calls == [vl.load_videos(EXAMPLE)[0].tep]
    assert "Đã mở thư mục" in p.status_var.get()


def test_chua_chon_dong_hoac_thieu_tep(root):
    calls = []
    p = make_panel(root, folder_opener=lambda path: (calls.append(path) or True, "ok"))
    p.mo_thu_muc()
    assert p.status_var.get() == "Chọn một dòng trước" and calls == []
    p.tree.selection_set("v4")  # A15: chưa có tệp
    p.mo_thu_muc()
    assert "chưa có đường dẫn tệp" in p.status_var.get() and calls == []


def test_loc_nen_tang_cap_nhat_thanh_phan_tram(root):
    p = make_panel(root)
    p.loc_nen_tang.set("youtube")
    p.ve_lai()
    assert len(p.tree.get_children()) == 2 and float(p.progress["value"]) == 50
    p.loc_nen_tang.set("tiktok")
    p.ve_lai()
    assert float(p.progress["value"]) == pytest.approx(33, abs=1)


def test_loi_mo_thu_muc_hien_ra_trong_thanh_trang_thai(root):
    p = make_panel(root, folder_opener=lambda path: (False, "Không thấy tệp lẫn thư mục"))
    p.tree.selection_set("v0")
    p.mo_thu_muc()
    assert p.status_var.get().startswith("A04: LỖI")


def test_menu_co_muc_mo_tep_trong_thu_muc(root):
    import video_links_ui as ui
    p = make_panel(root)
    menubar = ui.tao_menu(root, p)
    tep = menubar.nametowidget(menubar.entrycget(0, "menu"))
    assert "Mở tệp trong thư mục" in tep.entrycget(0, "label")
    assert "Mở thư mục chứa tệp" in p.btn_folder.cget("text")


def test_menu_chuot_phai_va_nut_thanh_cong_cu_cung_goi_mo_thu_muc(root):
    calls = []
    p = make_panel(root, folder_opener=lambda path: (calls.append(path) or True, "ok"))
    p.tree.selection_set("v1")
    p.btn_folder.invoke()
    p.context.invoke(0)
    assert len(calls) == 2


def test_mo_link_dung_trinh_mo_link(root):
    opened = []
    p = make_panel(root, link_opener=lambda url: (opened.append(url) or True, "Đã mở link trên trình duyệt"))
    p.tree.selection_set("v0")
    p.mo_link()
    assert opened == ["https://www.youtube.com/watch?v=EXAMPLE0001"]
