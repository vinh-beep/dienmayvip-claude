"""Kiểm duyệt video TRƯỚC khi xuất bản bằng OCR khung hình: chặn SĐT trên hình, chữ placeholder, từ cấm QC-2012.
Bản nâng cấp của _Shared/doc_anh_du_phong.py (anh Vĩnh gửi 27/10). Đóng băng an toàn: không mở được video,
không có OCR, không lấy được khung hình → CHẶN, không bao giờ "đủ điều kiện" vì thiếu dữ liệu.

Dùng trên PC:  pip install opencv-python pytesseract  (+ Tesseract có gói vie)
  python doc_anh_du_phong.py "D:\\20 Kenh MXH\\A04\\A04 - TikTok YouTube.mp4"
  python doc_anh_du_phong.py --kiem       # tự kiểm luật chữ, không cần cv2/tesseract
  python doc_anh_du_phong.py <video> --chi-tiet   # in thêm chữ OCR đọc được ở từng khung
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

# SĐT: OCR hay đọc "0912 345 678" / "0912.345.678" → chuẩn hóa dính số trước khi so; không bắt dãy dài hơn 10 số (IMEI, mã vạch)
MAU_SDT = re.compile(r"(?<!\d)(?:\+?84|0)[35789]\d{8}(?!\d)")
# Chữ placeholder / khung mẫu chưa thay (so sau khi bỏ dấu + chữ thường)
TU_PLACEHOLDER = ["keo/tai anh", "keo tai anh", "muc 3", "muc (3)", "placeholder", "anh hang thuc te", "lorem ipsum", "chen anh", "[anh]"]
# Luật QC-2012: cấm "số 1 / nhất / rẻ nhất / tốt nhất / hàng đầu / duy nhất" trên nội dung công khai
TU_CAM_QC = ["so 1", "so mot", "re nhat", "tot nhat", "hang dau", "duy nhat", "nhat viet nam", "nhat ben tre", "dan dau"]
GIAY_MAU_DAU = (1.0, 3.0, 5.0)
GIAY_MAU_CUOI = 3.0  # quét 3 giây cuối, tính theo độ dài thật của video


def bo_dau(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)  # NFKD: ③ → 3, ﬁ → fi
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D").lower()


def chuan_hoa_so(text: str) -> str:
    """Dính các cụm số bị OCR tách bằng khoảng trắng / chấm: '0912 345.678' → '0912345678'."""
    return re.sub(r"(?<=\d)[ .\-](?=\d)", "", text)


def kiem_van_ban(text: str, *, tu_cam_them: Iterable[str] = ()) -> tuple[bool, str]:
    """Luật chữ thuần, không cần OCR. Trả (hợp lệ, lý do)."""
    thuong = bo_dau(text)
    for kw in list(TU_PLACEHOLDER) + [bo_dau(k) for k in tu_cam_them]:
        if kw and kw in thuong:
            return False, f"Phát hiện chữ placeholder/cấm: '{kw}'"
    for kw in TU_CAM_QC:
        if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", thuong):
            return False, f"Vi phạm QC-2012: '{kw}'"
    if MAU_SDT.search(chuan_hoa_so(text)):
        return False, "Phát hiện SĐT trên hình (hotline chỉ được ghi ở mô tả bài)"
    return True, "OK"


def ocr_tesseract(frame_bgr: Any) -> str:
    import cv2
    import pytesseract

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(gray, lang="vie+eng")


def kiem_tra_khung_hinh_hop_le(frame_bgr: Any, *, ocr: Callable[[Any], str] = ocr_tesseract, tu_cam_them: Iterable[str] = ()) -> tuple[bool, str]:
    try:
        text = ocr(frame_bgr)
    except Exception as exc:  # thiếu tesseract/cv2, ảnh hỏng → chặn, không cho qua
        return False, f"Không OCR được khung hình ({exc.__class__.__name__}) → chặn để an toàn"
    return kiem_van_ban(text, tu_cam_them=tu_cam_them)


@dataclass
class KhungHinh:
    giay: float
    anh: Any


def lay_khung_hinh_cv2(video_path: str, giay: list[float]) -> tuple[float, list[KhungHinh]]:
    """Trả (độ dài giây, danh sách khung tại các giây yêu cầu). Độ dài 0 = không đọc được."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0.0, []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dai = total / fps if total > 0 else 0.0
    out: list[KhungHinh] = []
    for s in giay:
        idx = int(s * fps)
        if total and idx >= total:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok:
            out.append(KhungHinh(s, frame))
    cap.release()
    return dai, out


def giay_can_quet(dai: float) -> list[float]:
    """Đầu 1/3/5 s + 3 giây cuối tính theo độ dài thật (video 16 s vẫn quét 13/14/15 s)."""
    giay = [g for g in GIAY_MAU_DAU if g < dai]
    cuoi = max(dai - GIAY_MAU_CUOI, 0.0)
    for k in range(3):
        g = round(cuoi + k, 1)
        if g < dai and g not in giay:
            giay.append(g)
    return sorted(giay)


def kiem_duyet_video_truoc_render(
    video_path: str,
    *,
    lay_khung: Callable[[str, list[float]], tuple[float, list[KhungHinh]]] | None = None,
    ocr: Callable[[Any], str] = ocr_tesseract,
    tu_cam_them: Iterable[str] = (),
) -> tuple[bool, str]:
    lay_khung = lay_khung or lay_khung_hinh_cv2
    try:
        dai, _ = lay_khung(video_path, [])
    except Exception as exc:
        return False, f"Không mở được video ({exc.__class__.__name__}) → chặn"
    if dai <= 0:
        return False, "Không đọc được độ dài video → chặn"
    giay = giay_can_quet(dai)
    _, khung = lay_khung(video_path, giay)
    if not khung:
        return False, "Không lấy được khung hình nào → chặn"
    for kh in khung:
        ok, ly_do = kiem_tra_khung_hinh_hop_le(kh.anh, ocr=ocr, tu_cam_them=tu_cam_them)
        if not ok:
            return False, f"Chặn video tại giây {kh.giay:g}: {ly_do}"
    return True, f"Video đủ điều kiện xuất bản (đã quét {len(khung)} khung: {', '.join(f'{k.giay:g}s' for k in khung)})"


def tu_kiem() -> int:
    ca = [
        ("Samsung A04 giá 2.480.000đ tặng quà 237K", True),
        ("Hotline 0912 345 678", False), ("Zalo 0912.345.678", False), ("+84 912 345 678", False),
        ("IMEI 356789012345678", True), ("Mã đơn 090123456789012", True),
        ("Kéo/tải ảnh vào mục ③", False), ("ĐIỆN MÁY VIP giá rẻ nhất Bến Tre", False),
        ("Rẻ cho mọi nhà, bảo hành chính hãng", True), ("Số 1 Bến Tre", False), ("Nhất quán", True),
    ]
    hong = [(t, mong) for t, mong in ca if kiem_van_ban(t)[0] != mong]
    for t, mong in hong:
        print(f"HỎNG  {t!r} → mong {'qua' if mong else 'chặn'}, được {kiem_van_ban(t)}")
    print(f"Tự kiểm luật chữ: {len(ca) - len(hong)}/{len(ca)} đạt")
    return 1 if hong else 0


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] == "--kiem":
        return tu_kiem() if args else (print(__doc__) or 1)
    tu_cam: list[str] = []
    cfg = Path(__file__).with_name("tu-cam-them.json")
    if cfg.is_file():
        try:
            tu_cam = list(json.loads(cfg.read_text(encoding="utf-8-sig")))
        except ValueError:
            print("tu-cam-them.json hỏng, bỏ qua", file=sys.stderr)
    chi_tiet = "--chi-tiet" in args
    video = next((a for a in args if not a.startswith("--")), "")
    if not video:
        print(__doc__)
        return 1
    ocr = ocr_tesseract
    if chi_tiet:  # in chữ OCR đọc được ở từng khung để đối chiếu khi thử video thật
        def ocr(anh: Any) -> str:
            text = ocr_tesseract(anh)
            print("  OCR: " + " ".join(text.split())[:200])
            return text
    ok, ly_do = kiem_duyet_video_truoc_render(video, ocr=ocr, tu_cam_them=tu_cam)
    print(("ĐẠT  " if ok else "CHẶN ") + ly_do)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
