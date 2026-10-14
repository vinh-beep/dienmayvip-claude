"""Lõi VietQR (chuẩn Napas 247 / EMVCo), chạy offline hoàn toàn.

Đã đối chiếu: chuỗi tạo ra trùng từng ký tự với QR do SePay sinh (xem tests/).
QR chỉ chứa mã ngân hàng, số tài khoản nhận, số tiền, nội dung CK.
"""
import re
import unicodedata

from PIL import Image, ImageDraw, ImageFont

GHI_CHU_TOI_DA = 95  # tag 62 tối đa 99 ký tự, trừ 4 ký tự của tag con 08
MAU_NOI_DUNG = "{KHACH} thanh toan tien hang {SP} {SOTIEN}"


def tlv(tag, value):
    if len(value) > 99:
        raise ValueError(f"Trường {tag} dài {len(value)} ký tự, tối đa 99")
    return f"{tag}{len(value):02d}{value}"


def crc16(s):
    crc = 0xFFFF
    for b in s.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def khong_dau(text):
    """Bỏ dấu tiếng Việt và ký tự lạ: nhiều ngân hàng cắt hoặc lỗi nội dung có dấu."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9 .,\-/]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def noi_dung_ck(khach, san_pham, so_tien, mau=MAU_NOI_DUNG):
    """Ghép nội dung CK theo mẫu; rút gọn tên SP nếu vượt giới hạn QR."""
    khach = khong_dau(khach).upper()
    san_pham = khong_dau(san_pham)
    tien = str(int(so_tien)) if so_tien else ""

    def ghep(sp):
        return re.sub(r"\s+", " ", mau.format(KHACH=khach, SP=sp, SOTIEN=tien)).strip()

    note = ghep(san_pham)
    while len(note) > GHI_CHU_TOI_DA and " " in san_pham:
        san_pham = san_pham.rsplit(" ", 1)[0]
        note = ghep(san_pham)
    return note[:GHI_CHU_TOI_DA]


def payload(bin_, stk, so_tien=None, ghi_chu=None):
    if not re.fullmatch(r"\d{6}", bin_):
        raise ValueError("Mã ngân hàng (BIN) phải đủ 6 số")
    if not re.fullmatch(r"[0-9A-Za-z]{4,19}", stk):
        raise ValueError("Số tài khoản không hợp lệ")
    so_tien = int(so_tien) if so_tien else 0
    if so_tien < 0:
        raise ValueError("Số tiền âm")
    acc = tlv("00", bin_) + tlv("01", stk)
    guid = tlv("00", "A000000727") + tlv("01", acc) + tlv("02", "QRIBFTTA")
    s = tlv("00", "01") + tlv("01", "12" if so_tien else "11") + tlv("38", guid) + tlv("53", "704")
    if so_tien:
        s += tlv("54", str(so_tien))
    s += tlv("58", "VN")
    if ghi_chu:
        s += tlv("62", tlv("08", ghi_chu[:GHI_CHU_TOI_DA]))
    s += "6304"
    return s + crc16(s)


def _font(size):
    for p in (
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _chia_dong(text, font, max_w, draw):
    lines, cur = [], ""
    for w in text.split():
        thu = f"{cur} {w}".strip()
        if draw.textlength(thu, font=font) <= max_w or not cur:
            cur = thu
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def ve_qr(tai_khoan, so_tien=None, ghi_chu=None):
    """Trả về ảnh PIL: mã QR + tên NH, STK, chủ TK, số tiền, nội dung."""
    import qrcode

    ghi_chu = (ghi_chu or "")[:GHI_CHU_TOI_DA] or None
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(payload(tai_khoan["bin"], tai_khoan["stk"], so_tien, ghi_chu))
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    w, h = img.size
    nhap = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    dong = [(tai_khoan["bank"], 26), (tai_khoan["stk"], 30)]
    dong += [(t, 15) for t in _chia_dong(tai_khoan["name"], _font(15), w - 20, nhap)]
    if so_tien:
        dong.append((f"{int(so_tien):,} VND".replace(",", "."), 26))
    if ghi_chu:
        dong += [(t, 14) for t in _chia_dong(ghi_chu, _font(14), w - 20, nhap)]
    cao = sum(sz + 10 for _, sz in dong) + 16
    anh = Image.new("RGB", (w, h + cao), "white")
    anh.paste(img, (0, 0))
    d = ImageDraw.Draw(anh)
    y = h + 6
    for t, sz in dong:
        f = _font(sz)
        d.text(((w - d.textlength(t, font=f)) / 2, y), t, fill="black", font=f)
        y += sz + 10
    return anh
