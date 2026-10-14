"""Tạo ảnh VietQR từ dòng lệnh.
QR tĩnh cho mọi TK:  python vietqr_gen.py              -> out/
QR theo đơn:         python vietqr_gen.py --don ACB 42400000 "noi dung CK"
                     -> out/don-hang/ (không commit, có tên khách)"""
import json
import pathlib
import sys
import time

from vietqr_core import payload, ve_qr

HERE = pathlib.Path(__file__).parent


def tai_khoan():
    return json.loads((HERE / "accounts.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    accounts = tai_khoan()
    if len(sys.argv) == 5 and sys.argv[1] == "--don":
        a = next(x for x in accounts if x["code"] == sys.argv[2].upper())
        tien, note = int(sys.argv[3]), sys.argv[4]
        d = out / "don-hang"
        d.mkdir(exist_ok=True)
        f = d / f"VietQR_{a['code']}_{tien}_{time.strftime('%d %m %Y %Hh%Mp')}.png"
        ve_qr(a, tien, note).save(f)
        print("OK", f.name, "|", payload(a["bin"], a["stk"], tien, note))
        sys.exit()
    for a in accounts:
        f = out / f"VietQR_{a['code']}_{a['stk']}.png"
        ve_qr(a).save(f)
        print("OK", f.name, "|", payload(a["bin"], a["stk"]))
