"""Harness² VÒNG 2 cho bộ chặn của drive-sync: đo xem bộ chặn báo oan bao nhiêu lần.

Vòng 1 (kiem_an_toan.py) đoán trước: "tệp này nguy hiểm → chặn". Vòng 2 (tệp này) đo KẾT QUẢ THẬT:
anh xem lại tệp bị chặn và phán xử "oan" (tệp lành) hay "dung" (chặn đúng). Từ đó sinh sổ bài học
theo từng luật, kèm số mẫu; dưới 5 phán xử thì ghi "chưa đủ dữ liệu", không kết luận.

Vòng 1 lần sau đọc bai-hoc-chan.json: tệp nào anh đã phán "oan" (và nội dung còn y nguyên, so SHA-256)
thì đi qua — CHỈ với luật mềm. Luật cứng (bí mật, giá vốn, CCCD, tên tệp nhạy cảm) không bao giờ nới.

  python hoc_tu_chan.py --config dong_bo.config.json                      # đọc chan-*.txt + phán xử → sổ bài học
  python hoc_tu_chan.py --config dong_bo.config.json --phan-xu "BaoCao/a.pdf=oan" "BaoCao/b.csv=dung"
  python hoc_tu_chan.py --kiem                                            # bộ kiểm nhanh, không cần tệp thật

Mã Python thuần, 0 token. Không ghi nội dung tệp ra sổ, chỉ tên tệp + tên luật + con số.
Mã thoát: 0 ổn · 1 lỗi cấu hình/đầu vào.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiem_an_toan as an_toan  # noqa: E402
import dong_bo_drive  # noqa: E402  (dùng chung bộ đọc cấu hình + ép console UTF-8 trên Windows)

VN = timezone(timedelta(hours=7))
PHAN_XU_NAME = "phan-xu-chan.json"     # phán xử của anh (append, không xoá)
BAI_HOC_JSON = "bai-hoc-chan.json"     # máy sinh lại cả tệp mỗi lượt → vòng 1 đọc
BAI_HOC_MD = "so-bai-hoc-chan.md"      # máy sinh lại cả tệp mỗi lượt → người đọc
MAU_TOI_THIEU = 5                      # Harness²: dưới 5 mẫu = chưa đủ dữ liệu
NGUONG_DE_XUAT = 0.5                   # ≥50% oan (đủ mẫu) → đề xuất anh xem lại luật mềm
KET_LUAN_HOP_LE = ("oan", "dung")


class DauVaoLoi(ValueError):
    pass


def _now_vn(now: float | None) -> datetime:
    return datetime.fromtimestamp(now, VN) if now is not None else datetime.now(VN)


def _ghi_json_atomic(path: Path, data: Any) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _ghi_text_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------- đọc dữ liệu vòng 1


def doc_chan_logs(log_dir: Path) -> dict[str, dict[str, Any]]:
    """Gom mọi chan-*.txt → {dich/rel: {"luat": tên luật, "lan": số lần bị chặn, "cuoi": tên tệp log cuối}}.

    Dòng log: "<dich>/<rel>\\t<luat>[@<dòng>]". Dòng hỏng thì bỏ qua, không làm sập.
    """
    out: dict[str, dict[str, Any]] = {}
    for f in sorted(log_dir.glob("chan-*.txt")):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if "\t" not in line:
                continue
            path, why = line.split("\t", 1)
            path, why = path.strip(), why.strip()
            if not path or not why:
                continue
            rule = why.split("@", 1)[0]
            rec = out.setdefault(path, {"luat": rule, "lan": 0, "cuoi": f.name})
            rec["luat"] = rule  # luật ở lần chặn gần nhất
            rec["lan"] += 1
            rec["cuoi"] = f.name
    return out


def doc_phan_xu(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DauVaoLoi(f"Không đọc được {path.name}: {exc}") from exc
    raw = data.get("phan_xu") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict) and v.get("ket_luan") in KET_LUAN_HOP_LE:
            out[str(k)] = v
    return out


def _thu_muc_nguon(cfg: dict[str, Any]) -> dict[str, Path]:
    return {n["dich"]: Path(n["thu_muc"]) for n in cfg.get("nguon", []) if n.get("dich") and n.get("thu_muc")}


def them_phan_xu(
    cfg: dict[str, Any], cac_muc: list[str], *, now: float | None = None, ghi_chu: str = ""
) -> dict[str, dict[str, Any]]:
    """Ghi phán xử của anh vào phan-xu-chan.json (append/ghi đè theo tệp). Dạng mục: "<dich>/<rel>=oan|dung".

    Với "oan": băm SHA-256 tệp hiện tại để vòng 1 chỉ cho qua đúng nội dung này. Tệp không còn → vẫn ghi phán xử
    (để tính sổ) nhưng không có hash → không bao giờ được cho qua.
    """
    log_dir = Path(cfg["thu_muc_log"])
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / PHAN_XU_NAME
    hien_co = doc_phan_xu(path)
    nguon = _thu_muc_nguon(cfg)
    when = _now_vn(now).isoformat(timespec="seconds")
    for muc in cac_muc:
        if "=" not in muc:
            raise DauVaoLoi(f"Phán xử phải có dạng '<dich>/<rel>=oan|dung': {muc!r}")
        key, ket_luan = muc.rsplit("=", 1)
        key, ket_luan = key.strip().replace("\\", "/"), ket_luan.strip().lower()
        if ket_luan not in KET_LUAN_HOP_LE:
            raise DauVaoLoi(f"Kết luận chỉ nhận 'oan' hoặc 'dung': {muc!r}")
        if "/" not in key:
            raise DauVaoLoi(f"Thiếu tên đích trước dấu '/': {muc!r}")
        dich, rel = key.split("/", 1)
        if not rel or ".." in rel.split("/") or rel.startswith("/"):
            raise DauVaoLoi(f"Đường dẫn tệp không hợp lệ (không nhận '..'): {muc!r}")
        rec: dict[str, Any] = {"ket_luan": ket_luan, "ts": when}
        if ghi_chu:
            rec["ghi_chu"] = ghi_chu
        if ket_luan == "oan":
            root = nguon.get(dich)
            full = (root / rel) if root else None
            sha = an_toan.bam_tep(full) if full and full.is_file() else None
            if sha:
                rec["sha256"] = sha
            else:
                rec["canh_bao"] = "khong-thay-tep-khi-phan-xu"
        hien_co[key] = rec
    _ghi_json_atomic(path, {"ghi_chu": "Phán xử của chủ shop cho tệp bị chặn. oan = tệp lành, dung = chặn đúng. "
                                       "Chỉ thêm/ghi đè theo tệp; không xoá.", "phan_xu": hien_co})
    return hien_co


# ---------------------------------------------------------------- tổng hợp vòng 2


def tong_hop(
    chan: dict[str, dict[str, Any]],
    phan_xu: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Tính sổ bài học theo luật. Thuần hàm, không đụng đĩa — để kiểm thử dễ."""
    luat: dict[str, dict[str, Any]] = defaultdict(lambda: {"chan": 0, "tep": 0, "phan_xu": 0, "oan": 0, "dung": 0})
    for rec in chan.values():
        r = luat[rec["luat"]]
        r["chan"] += rec["lan"]
        r["tep"] += 1
    cho_phep_tep: dict[str, str] = {}
    bo_qua_cung: list[str] = []
    for key, px in phan_xu.items():
        rule = chan.get(key, {}).get("luat") or px.get("luat") or "khong-ro-luat"
        r = luat[rule]
        r["phan_xu"] += 1
        r[px["ket_luan"]] += 1
        if px["ket_luan"] == "oan":
            if rule in an_toan.LUAT_CUNG or rule == "khong-ro-luat":
                bo_qua_cung.append(key)
            elif px.get("sha256"):
                cho_phep_tep[key] = px["sha256"]

    de_xuat: list[str] = []
    for name, r in luat.items():
        r["cung"] = name in an_toan.LUAT_CUNG
        if r["phan_xu"] < MAU_TOI_THIEU:
            r["ty_le_oan"] = None
            r["do_tin"] = f"chưa đủ dữ liệu (<{MAU_TOI_THIEU} mẫu)"
        else:
            r["ty_le_oan"] = round(r["oan"] / r["phan_xu"], 3)
            r["do_tin"] = "đủ mẫu"
            if not r["cung"] and r["ty_le_oan"] >= NGUONG_DE_XUAT:
                de_xuat.append(
                    f"Luật mềm '{name}' báo oan {r['oan']}/{r['phan_xu']} lần đã phán xử → anh xem lại nguồn/"
                    f"cấu hình (ví dụ cho_phep_duoi_khong_quet). Máy KHÔNG tự nới luật."
                )
            if r["cung"] and r["ty_le_oan"] >= NGUONG_DE_XUAT:
                de_xuat.append(
                    f"Luật CỨNG '{name}' bị phán oan {r['oan']}/{r['phan_xu']} → chỉ ghi nhận, giữ chặn. "
                    f"Muốn đổi luật cứng phải sửa mã + anh duyệt."
                )
    return {
        "luat": dict(sorted(luat.items())),
        "cho_phep_tep": dict(sorted(cho_phep_tep.items())),
        "bo_qua_vi_luat_cung": sorted(bo_qua_cung),
        "de_xuat": de_xuat,
        "chua_phan_xu": sorted(k for k in chan if k not in phan_xu),
    }


def _md(tong: dict[str, Any], chan: dict[str, dict[str, Any]], phan_xu: dict[str, dict[str, Any]], when: datetime) -> str:
    out = [
        "# Sổ bài học BỘ CHẶN drive-sync — Harness² vòng 2 (máy tự sinh, mới nhất trên cùng)",
        f"Cập nhật {when.strftime('%d/%m/%Y %H:%M')} (giờ VN) · nguồn: hoc_tu_chan.py · chỉ tên tệp, tên luật và con số; "
        "không có nội dung tệp.",
        "",
        "Luật cứng (bí mật, giá vốn, CCCD, tên tệp nhạy cảm) không bao giờ nới dù bị phán oan. "
        "Luật mềm: tệp anh phán \"oan\" đi qua khi nội dung còn y nguyên (SHA-256). "
        "Chốt chặn không áp 80/20: không thử nới luật để xem có lọt không.",
        "",
        "## ① Chấm từng luật",
        "| Luật | Loại | Lần chặn | Tệp | Đã phán xử | Oan | Tỉ lệ oan | Độ tin |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rows = sorted(tong["luat"].items(), key=lambda kv: (-kv[1]["phan_xu"], -kv[1]["chan"], kv[0]))
    for name, r in rows:
        ty = "—" if r["ty_le_oan"] is None else f"{r['ty_le_oan'] * 100:.0f}%"
        out.append(f"| {name} | {'cứng' if r['cung'] else 'mềm'} | {r['chan']} | {r['tep']} | {r['phan_xu']} | {r['oan']} | {ty} | {r['do_tin']} |")
    if not rows:
        out.append("| (chưa có lần chặn nào) | | | | | | | |")

    out += ["", "## ② Đề xuất (máy chỉ đề xuất, anh quyết)"]
    out += [f"- {d}" for d in tong["de_xuat"]] or ["- Chưa có."]

    out += ["", f"## ③ Tệp được đi qua nhờ phán xử \"oan\" ({len(tong['cho_phep_tep'])})"]
    out += [f"- {k} · sha256 {v[:12]}…" for k, v in tong["cho_phep_tep"].items()] or ["- Không có."]
    if tong["bo_qua_vi_luat_cung"]:
        out += ["", "Phán \"oan\" nhưng KHÔNG cho qua vì luật cứng:"] + [f"- {k}" for k in tong["bo_qua_vi_luat_cung"]]

    out += ["", "## ④ Từng phán xử (mới nhất trên cùng)", "| Thời điểm | Tệp | Luật | Kết luận | Ghi chú |", "|---|---|---|---|---|"]
    px_rows = sorted(phan_xu.items(), key=lambda kv: kv[1].get("ts", ""), reverse=True)
    for key, px in px_rows:
        rule = chan.get(key, {}).get("luat", "?")
        note = px.get("ghi_chu", "") or ("" if px.get("sha256") or px["ket_luan"] == "dung" else "không thấy tệp lúc phán xử")
        out.append(f"| {px.get('ts', '')} | {key} | {rule} | {px['ket_luan']} | {note} |")
    if not px_rows:
        out.append("| (chưa có phán xử) | | | | |")

    chua = tong["chua_phan_xu"]
    out += ["", f"## ⑤ Chờ anh phán xử ({len(chua)})",
            "Lệnh: `python hoc_tu_chan.py --config dong_bo.config.json --phan-xu \"<tệp>=oan\"` hoặc `=dung`."]
    out += [f"- {k} · {chan[k]['luat']} · chặn {chan[k]['lan']} lần" for k in chua[:200]] or ["- Không còn."]
    if len(chua) > 200:
        out.append(f"- … và {len(chua) - 200} tệp nữa")
    return "\n".join(out) + "\n"


def chay_vong_2(cfg: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """Đọc chan-*.txt + phan-xu-chan.json → ghi bai-hoc-chan.json + so-bai-hoc-chan.md. Trả về bảng tổng hợp."""
    log_dir = Path(cfg["thu_muc_log"])
    log_dir.mkdir(parents=True, exist_ok=True)
    when = _now_vn(now)
    chan = doc_chan_logs(log_dir)
    phan_xu = doc_phan_xu(log_dir / PHAN_XU_NAME)
    tong = tong_hop(chan, phan_xu)
    tong["ts"] = when.isoformat(timespec="seconds")
    tong["mau_toi_thieu"] = MAU_TOI_THIEU
    _ghi_json_atomic(log_dir / BAI_HOC_JSON, tong)
    _ghi_text_atomic(log_dir / BAI_HOC_MD, _md(tong, chan, phan_xu, when))
    return tong


# ---------------------------------------------------------------- bộ kiểm nhanh (--kiem)


def kiem_nhanh() -> list[str]:
    """Kiểm logic cốt lõi không cần tệp thật. Trả về danh sách lỗi (rỗng = đạt)."""
    loi: list[str] = []
    chan = {
        "BaoCao/a.pdf": {"luat": "loai-tep-khong-quet-duoc", "lan": 3, "cuoi": "chan-x.txt"},
        "BaoCao/b.csv": {"luat": "so-dien-thoai-vn", "lan": 1, "cuoi": "chan-x.txt"},
        "BaoCao/c.txt": {"luat": "khoa-api-google", "lan": 1, "cuoi": "chan-x.txt"},
    }
    px = {
        "BaoCao/a.pdf": {"ket_luan": "oan", "ts": "2026-10-25T22:00:00+07:00", "sha256": "f" * 64},
        "BaoCao/c.txt": {"ket_luan": "oan", "ts": "2026-10-25T22:01:00+07:00", "sha256": "e" * 64},
    }
    t = tong_hop(chan, px)
    if t["cho_phep_tep"] != {"BaoCao/a.pdf": "f" * 64}:
        loi.append("luật mềm + oan + sha phải vào cho_phep_tep")
    if t["bo_qua_vi_luat_cung"] != ["BaoCao/c.txt"]:
        loi.append("luật cứng bị phán oan phải bị bỏ qua")
    if t["luat"]["loai-tep-khong-quet-duoc"]["do_tin"] != f"chưa đủ dữ liệu (<{MAU_TOI_THIEU} mẫu)":
        loi.append("dưới 5 mẫu phải ghi chưa đủ dữ liệu")
    if t["chua_phan_xu"] != ["BaoCao/b.csv"]:
        loi.append("tệp chưa phán xử phải được liệt kê")
    px5 = {f"BaoCao/{i}.pdf": {"ket_luan": "oan", "ts": "t", "sha256": "a" * 64} for i in range(5)}
    chan5 = {k: {"luat": "loai-tep-khong-quet-duoc", "lan": 1, "cuoi": "c"} for k in px5}
    t5 = tong_hop(chan5, px5)
    if t5["luat"]["loai-tep-khong-quet-duoc"]["ty_le_oan"] != 1.0 or not t5["de_xuat"]:
        loi.append("đủ 5 mẫu, 100% oan phải ra tỉ lệ 1.0 và có đề xuất")
    if not an_toan.LUAT_CUNG.isdisjoint(an_toan.LUAT_MEM):
        loi.append("luật cứng và luật mềm không được giao nhau")
    if "gia-von-ncc" not in an_toan.LUAT_CUNG or "khoa-rieng" not in an_toan.LUAT_CUNG:
        loi.append("giá vốn và khoá riêng phải là luật cứng")
    return loi


def main(argv: list[str] | None = None) -> int:
    dong_bo_drive._utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="dong_bo.config.json (cùng tệp với dong_bo_drive.py)")
    ap.add_argument("--phan-xu", nargs="+", metavar="DICH/REL=oan|dung", help="ghi phán xử của anh rồi tính lại sổ")
    ap.add_argument("--ghi-chu", default="", help="ghi chú ngắn kèm phán xử (không ghi nội dung tệp)")
    ap.add_argument("--kiem", action="store_true", help="bộ kiểm nhanh, không cần tệp thật")
    args = ap.parse_args(argv)

    if args.kiem:
        loi = kiem_nhanh()
        print("KIỂM: " + ("ĐẠT" if not loi else "LỖI"))
        for l in loi:
            print(" -", l)
        return 0 if not loi else 1
    if not args.config:
        print("Cần --config (hoặc --kiem)", file=sys.stderr)
        return 1
    try:
        cfg = dong_bo_drive.load_config(Path(args.config))
        if args.phan_xu:
            them_phan_xu(cfg, args.phan_xu, ghi_chu=args.ghi_chu)
        tong = chay_vong_2(cfg)
    except (dong_bo_drive.ConfigError, DauVaoLoi) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    n_luat = len(tong["luat"])
    print(f"Sổ bài học: {n_luat} luật · {len(tong['cho_phep_tep'])} tệp đi qua nhờ phán xử · "
          f"{len(tong['chua_phan_xu'])} tệp chờ phán xử · {len(tong['de_xuat'])} đề xuất")
    print(f"Tệp: {Path(cfg['thu_muc_log']) / BAI_HOC_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
