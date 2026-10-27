import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import video_links as vl  # noqa: E402

EXAMPLE = Path(__file__).resolve().parent.parent / "so_video.example.json"


# ---------------------------------------------------------------- nhận dạng link


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://m.youtube.com/watch?v=abc", "youtube"),
    ("https://youtu.be/abc", "youtube"),
    ("https://www.tiktok.com/@dienmayvip/video/1", "tiktok"),
    ("https://vm.tiktok.com/ZMabc/", "tiktok"),
    ("https://youtube.com.evil.example/x", "khac"),
    ("https://notyoutube.com/x", "khac"),
    ("https://faketiktok.com/x", "khac"),
    ("", "khac"),
])
def test_nhan_dang_nen_tang(url, expected):
    assert vl.detect_platform(url) == expected


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "file:///C:/Windows/System32/calc.exe", "data:text/html,x",
                                 "ftp://x.com/a", "", "   ", "https://", None, "C:\\a.mp4"])
def test_chi_nhan_link_http_https(bad):
    assert vl.clean_url(bad) == ""


def test_link_hop_le_duoc_giu():
    assert vl.clean_url("  https://youtu.be/abc  ") == "https://youtu.be/abc"


# ---------------------------------------------------------------- chuẩn hóa


def test_trang_thai_va_tien_do_tu_suy():
    v = vl.normalize({"ma": "A1", "url": "https://youtu.be/x", "tien_do": 100})
    assert v.trang_thai == "da-dang" and v.nen_tang == "youtube" and v.tien_do == 100
    assert vl.normalize({"ma": "A2", "tien_do": 40}).trang_thai == "dang-dang"
    assert vl.normalize({"ma": "A3"}).trang_thai == "cho-dang"


def test_tien_do_bi_chan_0_100_va_da_dang_la_100():
    assert vl.normalize({"tien_do": 250}).tien_do == 100
    assert vl.normalize({"tien_do": -5}).tien_do == 0
    assert vl.normalize({"tien_do": "abc"}).tien_do == 0
    assert vl.normalize({"tien_do": "60%"}).tien_do == 60
    assert vl.normalize({"trang_thai": "da-dang", "tien_do": 10}).tien_do == 100


def test_link_xau_bi_bo_khoi_du_lieu():
    v = vl.normalize({"url": "javascript:alert(1)", "tien_do": 100})
    assert v.url == "" and v.trang_thai != "da-dang"


def test_nen_tang_khai_tay_duoc_ton_trong_nhung_gia_tri_la_bi_bo():
    assert vl.normalize({"nen_tang": "TikTok"}).nen_tang == "tiktok"
    assert vl.normalize({"nen_tang": "myspace", "url": "https://youtu.be/x"}).nen_tang == "youtube"


# ---------------------------------------------------------------- nạp tệp


def test_nap_json_dang_dict_va_list(tmp_path):
    recs = [{"ma": "A1", "url": "https://youtu.be/x", "tien_do": 100}]
    (tmp_path / "a.json").write_text(json.dumps({"videos": recs}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(recs), encoding="utf-8")
    assert [v.ma for v in vl.load_videos(tmp_path / "a.json")] == ["A1"]
    assert [v.ma for v in vl.load_videos(tmp_path / "b.json")] == ["A1"]


def test_nap_csv_co_bom_va_tieng_viet(tmp_path):
    p = tmp_path / "v.csv"
    p.write_text("ma,ten,url,tep,trang_thai,tien_do\nA1,Điện thoại Samsung,https://youtu.be/x,D:\\a.mp4,da-dang,100\n",
                 encoding="utf-8-sig")
    v = vl.load_videos(p)[0]
    assert v.ten == "Điện thoại Samsung" and v.nen_tang == "youtube"


def test_vi_du_dung_duoc():
    videos = vl.load_videos(EXAMPLE)
    assert len(videos) == 5
    s = vl.tong_ket(videos)
    assert s["da_dang"] == 2 and s["ti_le_da_dang"] == 40


# ---------------------------------------------------------------- tổng kết


def test_tong_ket_theo_nen_tang():
    videos = vl.load_videos(EXAMPLE)
    s = vl.tong_ket(videos)
    assert s["tong"] == 5 and s["tien_do_trung_binh"] == round((100 + 100 + 60 + 0 + 0) / 5)
    assert s["theo_nen_tang"]["youtube"] == {"tong": 2, "da_dang": 1, "loi": 0, "thieu_link": 1}
    assert s["theo_nen_tang"]["tiktok"]["loi"] == 1
    assert s["thieu_link"] == ["A06", "A07", "A15"] and s["thieu_tep"] == ["A15"]


def test_tong_ket_rong_khong_chia_cho_0():
    s = vl.tong_ket([])
    assert s["tong"] == 0 and s["ti_le_da_dang"] == 0 and s["tien_do_trung_binh"] == 0


def test_kiem_tep_con_ton_tai(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    videos = [vl.normalize({"ma": "OK", "tep": str(f)}), vl.normalize({"ma": "MAT", "tep": str(tmp_path / "khong-co.mp4")})]
    assert vl.tong_ket(videos, kiem_tep=True)["tep_khong_con"] == ["MAT"]
    assert "tep_khong_con" not in vl.tong_ket(videos)


def test_markdown_co_link_theo_nen_tang():
    md = vl.tom_tat_markdown(vl.load_videos(EXAMPLE))
    assert "đã đăng 2/5 (40%)" in md and "## YouTube" in md and "## TikTok" in md
    assert "https://www.youtube.com/watch?v=EXAMPLE0001" in md
    assert vl.tom_tat_markdown([]).startswith("# Tổng kết video — đã đăng 0/0")


# ---------------------------------------------------------------- mở tệp trong thư mục


class Rec:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)


def test_windows_chon_san_tep_bang_explorer_select():
    r = Rec()
    ok, msg = vl.open_in_folder("C:\\Kho anh\\A04 video.mp4", platform="win32", runner=r, exists=lambda p: True)
    assert ok and r.calls == ['explorer /select,"C:\\Kho anh\\A04 video.mp4"']
    assert "chọn sẵn" in msg


def test_mac_va_linux():
    r = Rec()
    vl.open_in_folder("/Users/a/v.mp4", platform="darwin", runner=r, exists=lambda p: True)
    vl.open_in_folder("/home/a/v.mp4", platform="linux", runner=r, exists=lambda p: True)
    assert r.calls == [["open", "-R", "/Users/a/v.mp4"], ["xdg-open", "/home/a"]]


def test_tep_mat_van_mo_thu_muc_chua_no():
    r = Rec()
    ok, msg = vl.open_in_folder("/home/a/b/v.mp4", platform="linux", runner=r, exists=lambda p: False, isdir=lambda p: True)
    assert ok and r.calls == [["xdg-open", "/home/a/b"]] and "không còn" in msg


def test_khong_thay_ca_tep_lan_thu_muc():
    r = Rec()
    ok, msg = vl.open_in_folder("/x/y/v.mp4", platform="linux", runner=r, exists=lambda p: False, isdir=lambda p: False)
    assert not ok and r.calls == []


@pytest.mark.parametrize("bad", ["", 'C:\\a" & calc.exe & "b.mp4', "C:\\a\nb.mp4", "C:\\a\x00b.mp4"])
def test_duong_dan_nguy_hiem_khong_bao_gio_duoc_chay(bad):
    r = Rec()
    ok, _ = vl.open_in_folder(bad, platform="win32", runner=r, exists=lambda p: True)
    assert not ok and r.calls == []


def test_open_link_chi_mo_http():
    opened = []
    assert vl.open_link("https://youtu.be/x", opener=opened.append)[0] is True and opened == ["https://youtu.be/x"]
    assert vl.open_link("javascript:alert(1)", opener=opened.append)[0] is False and len(opened) == 1
    assert vl.open_link("", opener=opened.append)[0] is False


def test_cli_khong_sap_khi_console_cp1252(tmp_path):
    import os
    import subprocess
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(Path(vl.__file__)), str(EXAMPLE)], capture_output=True, env=env, timeout=60)
    assert b"Traceback" not in proc.stderr, proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 0 and "Tổng kết video".encode("utf-8") in proc.stdout


# ---------------------------------------------------------------- --kiem (chuẩn app Harness²)


def test_tu_kiem_dat_va_lenh_kiem_ma_0(capsys):
    assert vl.tu_kiem() == []
    assert vl.main(["--kiem"]) == 0
    assert "KIỂM: ĐẠT" in capsys.readouterr().out
