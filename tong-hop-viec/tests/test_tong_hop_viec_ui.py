import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
tk = pytest.importorskip("tkinter")

import tong_hop_viec as th  # noqa: E402
from test_tong_hop_viec import NOW, kho  # noqa: E402,F401


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("không có màn hình")
    r.withdraw()
    yield r
    r.destroy()


def test_panel_chep_tat_ca_va_muc(root, kho, tmp_path):
    import tong_hop_viec_ui as ui
    kq = th.chay([kho[0], kho[1]], tmp_path / "ra", bay_gio=NOW)
    p = ui.TongHopPanel(root, kq)
    assert float(p.progress["value"]) == kq["ti_le_xong"]
    assert p.list.size() == 1 + len(kq["danh_muc"])
    p.chep_tat_ca()
    clip = root.clipboard_get()
    assert "TỔNG HỢP VIỆC CÒN MỞ" in clip and "Lazada" in clip and "0903" not in clip
    p.list.selection_clear(0, "end")
    p.list.selection_set(1)
    p.chep_muc()
    assert "==" in root.clipboard_get()
    assert "✅" not in p.text.get("1.0", "end")  # đang lọc chỉ việc còn mở
    p.list.selection_clear(0, "end")
    p.list.selection_set(0)                      # mục "Tất cả"
    p.chi_mo.set(False)
    p.ve_lai()
    assert "✅" in p.text.get("1.0", "end")
