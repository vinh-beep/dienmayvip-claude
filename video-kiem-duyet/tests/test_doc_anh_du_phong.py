import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import doc_anh_du_phong as da  # noqa: E402


@pytest.mark.parametrize("text,ok", [
    ("Samsung A04 4GB 64GB giá 2.480.000đ tặng bộ quà 237K", True),
    ("Hotline: 0912 345 678", False), ("Zalo 0912.345.678", False), ("0912345678", False), ("+84 912 345 678", False),
    ("IMEI 356789012345678", True), ("Mã vận đơn 090123456789012", True), ("Giá 3.890.000", True),
    ("Kéo/tải ảnh vào đây", False), ("xem mục ③", False), ("ảnh hàng thực tế", False), ("PLACEHOLDER", False),
    ("Giá rẻ nhất Bến Tre", False), ("Điện Máy VIP số 1 Bến Tre", False), ("hàng đầu Việt Nam", False), ("duy nhất hôm nay", False),
    ("VIP giá rẻ cho mọi nhà", True), ("Nhất quán chất lượng", True), ("Tốt nhất", False), ("tot nhat (OCR mất dấu)", False),
])
def test_luat_chu(text, ok):
    assert da.kiem_van_ban(text)[0] is ok, da.kiem_van_ban(text)


def test_tu_cam_them_tu_cau_hinh():
    assert da.kiem_van_ban("khuyến mãi SIÊU KHỦNG", tu_cam_them=["siêu khủng"])[0] is False
    assert da.kiem_van_ban("khuyến mãi SIÊU KHỦNG")[0] is True


def test_giay_can_quet_theo_do_dai_that():
    assert da.giay_can_quet(21) == [1, 3, 5, 18, 19, 20]
    assert da.giay_can_quet(16) == [1, 3, 5, 13, 14, 15]
    assert da.giay_can_quet(4) == [1, 2, 3]
    assert da.giay_can_quet(2.5) == [0, 1, 2]  # video rất ngắn: quét từ khung đầu, không trùng giây


def fake_lay(frames: dict[float, str], dai: float):
    def _lay(path, giay):
        return dai, [da.KhungHinh(g, frames.get(g, "")) for g in giay]
    return _lay


def test_video_sach_qua():
    ok, msg = da.kiem_duyet_video_truoc_render("x.mp4", lay_khung=fake_lay({}, 18), ocr=lambda t: "Samsung A04 giá 2.480.000")
    assert ok and "6 khung" in msg


def test_sdt_o_giay_cuoi_bi_chan_dung_giay():
    frames = {17.0: "Hotline 0912 345 678"}
    ok, msg = da.kiem_duyet_video_truoc_render("x.mp4", lay_khung=fake_lay(frames, 18), ocr=lambda t: t)
    assert not ok and "giây 17" in msg and "SĐT" in msg


def test_placeholder_dau_video_bi_chan():
    ok, msg = da.kiem_duyet_video_truoc_render("x.mp4", lay_khung=fake_lay({1.0: "Kéo/tải ảnh"}, 18), ocr=lambda t: t)
    assert not ok and "giây 1" in msg


@pytest.mark.parametrize("lay,chua", [
    (lambda p, g: (0.0, []), "độ dài"),
    (lambda p, g: (18.0, []), "khung hình"),
    (lambda p, g: (_ for _ in ()).throw(OSError("codec")), "Không mở được"),
])
def test_dong_bang_an_toan_khi_khong_doc_duoc(lay, chua):
    ok, msg = da.kiem_duyet_video_truoc_render("x.mp4", lay_khung=lay, ocr=lambda t: "")
    assert not ok and chua in msg


def test_ocr_loi_thi_chan_khong_cho_qua():
    def ocr_hong(frame):
        raise RuntimeError("tesseract is not installed")
    ok, msg = da.kiem_duyet_video_truoc_render("x.mp4", lay_khung=fake_lay({}, 18), ocr=ocr_hong)
    assert not ok and "Không OCR" in msg


def test_khong_co_sdt_that_trong_ma_nguon_va_test():
    for f in (Path(da.__file__), Path(__file__), Path(da.__file__).with_name("README.md")):
        text = da.chuan_hoa_so(f.read_text(encoding="utf-8"))
        hotline_dau = "09" + "03"  # ghép lúc chạy để chính ca kiểm này không chứa số thật
        assert hotline_dau not in text, f"{f.name} chứa số hotline thật"
        for m in da.MAU_SDT.findall(text):
            assert m.endswith("912345678"), f"{f.name} chứa SĐT không phải số giả: {m}"


def test_cli_tu_kiem_va_cp1252():
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(Path(da.__file__)), "--kiem"], capture_output=True, env=env, timeout=60)
    assert b"Traceback" not in proc.stderr and proc.returncode == 0, proc.stdout + proc.stderr
    assert "11/11".encode("utf-8") in proc.stdout
