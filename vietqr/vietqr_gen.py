"""Tạo mã VietQR (chuẩn Napas 247) tĩnh cho từng tài khoản trong accounts.json.
Chạy: python vietqr_gen.py  -> QR tĩnh cho mọi TK, ra out/
QR theo đơn: python vietqr_gen.py --don ACB 42400000 "noi dung CK"  -> out/don-hang/ (không commit, có tên khách)
Chỉ chứa thông tin NHẬN TIỀN (mã NH + STK). Không có số dư/giá vốn."""
import json, pathlib, qrcode
from PIL import Image, ImageDraw, ImageFont

def tlv(i, v): return f"{i}{len(v):02d}{v}"

def crc16(s):
    crc = 0xFFFF
    for b in s.encode():
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"

def payload(bin_, stk, amount=None, note=None):
    acc = tlv("00", bin_) + tlv("01", stk)
    guid = tlv("00", "A000000727") + tlv("01", acc) + tlv("02", "QRIBFTTA")
    s = tlv("00", "01") + tlv("01", "12" if amount else "11") + tlv("38", guid) + tlv("53", "704")
    if amount: s += tlv("54", str(int(amount)))
    s += tlv("58", "VN")
    if note: s += tlv("62", tlv("08", note))
    s += "6304"
    return s + crc16(s)

def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        try: return ImageFont.truetype(p, sz)
        except OSError: pass
    return ImageFont.load_default()

def make(acc, out):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(payload(acc["bin"], acc["stk"], acc.get("amount"), acc.get("note")))
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    w, h = img.size
    canvas = Image.new("RGB", (w, h + 175), "white")
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    words = acc["name"].split(); mid = len(words) // 2 + len(words) % 2
    lines = [(acc["bank"], 26), (acc["stk"], 30), (" ".join(words[:mid]), 15), (" ".join(words[mid:]), 15)]
    for i, (t, sz) in enumerate(lines):
        tw = d.textlength(t, font=font(sz))
        d.text(((w - tw) / 2, h + 8 + [0, 38, 80, 102][i]), t, fill="black", font=font(sz))
    canvas.save(out)

if __name__ == "__main__":
    import sys, time
    here = pathlib.Path(__file__).parent
    out = here / "out"; out.mkdir(exist_ok=True)
    accounts = json.loads((here / "accounts.json").read_text(encoding="utf-8"))
    if len(sys.argv) == 5 and sys.argv[1] == "--don":
        a = next(x for x in accounts if x["code"] == sys.argv[2].upper())
        a = dict(a, amount=int(sys.argv[3]), note=sys.argv[4])
        d = out / "don-hang"; d.mkdir(exist_ok=True)
        f = d / f"VietQR_{a['code']}_{a['amount']}_{time.strftime('%d %m %Y %Hh%Mp')}.png"
        make(a, f); print("OK", f.name, "|", payload(a["bin"], a["stk"], a["amount"], a["note"]))
        sys.exit()
    for a in accounts:
        f = out / f"VietQR_{a['code']}_{a['stk']}.png"
        make(a, f); print("OK", f.name, "|", payload(a["bin"], a["stk"]))
