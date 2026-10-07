"""Đẩy thư mục đã chọn lên Google Drive bằng rclone copy (chỉ thêm/cập nhật, không xóa).

Mặc định CHẠY THỬ (--dry-run). Chỉ ghi lên Drive khi có cờ --chay-that.
  python dong_bo_drive.py --config dong_bo.config.json            # chạy thử
  python dong_bo_drive.py --config dong_bo.config.json --chay-that
  python dong_bo_drive.py --config dong_bo.config.json --kiem-tuoi # báo nếu >24 giờ chưa đẩy được

Không gọi AI nào → 0 token. Mã thoát: 0 ổn · 1 có lỗi · 2 quá hạn chưa đồng bộ.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiem_an_toan as an_toan  # noqa: E402

VN = timezone(timedelta(hours=7))
STATUS_NAME = "trang-thai-dong-bo.json"
LOCK_STALE_S = 2 * 3600


class ConfigError(ValueError):
    pass


def parse_size(text: str) -> int:
    m = re.fullmatch(r"\s*(\d+)\s*([KMG]?)B?\s*", str(text), re.IGNORECASE)
    if not m:
        raise ConfigError(f"Dung lượng không hợp lệ: {text!r} (ví dụ 50M)")
    return int(m.group(1)) * {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}[m.group(2).upper()]


def parse_age(text: str) -> float:
    m = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", str(text), re.IGNORECASE)
    if not m:
        raise ConfigError(f"Thời gian không hợp lệ: {text!r} (ví dụ 2d, 12h, 30m)")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2).lower()]


def load_config(path: Path) -> dict[str, Any]:
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Không đọc được {path}: {exc}") from exc
    for key in ("remote", "nguon", "thu_muc_log"):
        if not cfg.get(key):
            raise ConfigError(f"Thiếu mục '{key}' trong cấu hình")
    if not str(cfg["remote"]).endswith(":"):
        raise ConfigError("'remote' phải kết thúc bằng dấu : (ví dụ dmv-drive:)")
    for n in cfg["nguon"]:
        if not n.get("thu_muc") or not n.get("dich"):
            raise ConfigError("Mỗi mục trong 'nguon' cần 'thu_muc' và 'dich'")
        if re.fullmatch(r"[A-Za-z]:[\\/]*", n["thu_muc"].strip()):
            raise ConfigError(f"Không được đẩy cả ổ đĩa: {n['thu_muc']}")
        if re.search(r"[\\/]desktop[\\/]*$", n["thu_muc"].strip(), re.IGNORECASE):
            raise ConfigError(f"Không được đẩy cả Desktop: {n['thu_muc']}")
        if "/" in n["dich"] or "\\" in n["dich"] or n["dich"] in (".", ".."):
            raise ConfigError(f"'dich' chỉ là một tên thư mục đơn: {n['dich']!r}")
    cfg.setdefault("max_size", "50M")
    cfg.setdefault("max_age", "2d")
    cfg.setdefault("min_age", "1m")
    cfg.setdefault("rclone", "rclone")
    cfg.setdefault("bao_loi_sau_gio", 24)
    cfg.setdefault("cho_phep_duoi_khong_quet", [])
    parse_size(cfg["max_size"]), parse_age(cfg["max_age"]), parse_age(cfg["min_age"])
    return cfg


def build_rclone_cmd(cfg: dict[str, Any], src: str, dest: str, list_file: Path, log_file: Path, *, chay_that: bool) -> list[str]:
    cmd = [
        cfg["rclone"], "copy", src, f"{cfg['remote']}{dest}",
        "--files-from", str(list_file),
        "--max-size", str(cfg["max_size"]),
        "--log-file", str(log_file), "--log-level", "INFO", "--stats-one-line",
        "--transfers", "4", "--checkers", "8",
    ]
    if not chay_that:
        cmd.append("--dry-run")
    return cmd


def _now_vn(now: float | None) -> datetime:
    return datetime.fromtimestamp(now, VN) if now is not None else datetime.now(VN)


def _write_json_atomic(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class Lock:
    """Chống chạy chồng: tạo tệp khóa; khóa cũ hơn 2 giờ coi như bỏ."""

    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self):
        for _ in range(2):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE_S:
                        self.path.unlink()
                        continue
                except OSError:
                    pass
                raise RuntimeError("Đang có lượt đồng bộ khác chạy")
        raise RuntimeError("Không tạo được tệp khóa")

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)
            try:
                self.path.unlink()
            except OSError:
                pass


def chay_dong_bo(
    cfg: dict[str, Any],
    *,
    chay_that: bool,
    now: float | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    now_ts = now if now is not None else time.time()
    when = _now_vn(now_ts)
    log_dir = Path(cfg["thu_muc_log"])
    log_dir.mkdir(parents=True, exist_ok=True)
    max_size = parse_size(cfg["max_size"])
    max_age = parse_age(cfg["max_age"])
    min_age = parse_age(cfg["min_age"])
    extra = frozenset(e.lower() for e in cfg["cho_phep_duoi_khong_quet"])
    stamp = when.strftime("%Y%m%d-%H%M%S")

    status_path = log_dir / STATUS_NAME
    previous: dict[str, Any] = {}
    if status_path.is_file():
        try:
            previous = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}

    status: dict[str, Any] = {
        "ts": when.isoformat(timespec="seconds"),
        "che_do": "that" if chay_that else "chay-thu",
        "ket_qua": "ok",
        "thu_muc": [],
        "loi": [],
        "lan_thanh_cong_cuoi": previous.get("lan_thanh_cong_cuoi"),
    }
    chan_lines: list[str] = []

    with Lock(log_dir / "dong-bo.lock"):
        for item in cfg["nguon"]:
            src = Path(item["thu_muc"])
            entry: dict[str, Any] = {"dich": item["dich"], "tim_thay": 0, "se_day": 0, "bi_chan": 0, "bo_qua": {}, "rclone_ma": None}
            if not src.is_dir():
                status["loi"].append(f"Không thấy thư mục nguồn của '{item['dich']}'")
                entry["loi"] = "khong-thay-thu-muc"
                status["thu_muc"].append(entry)
                continue
            scan = an_toan.quet_thu_muc(
                src, max_size=max_size, max_age_s=max_age, min_age_s=min_age, now=now_ts,
                cho_phep_khong_quet=extra,
            )
            entry.update(
                tim_thay=scan.seen, se_day=len(scan.allowed), bi_chan=len(scan.blocked),
                bo_qua=dict(scan.skipped), dung_luong_byte=scan.allowed_bytes,
            )
            by_rule: dict[str, int] = {}
            for rel, why in scan.blocked.items():
                chan_lines.append(f"{item['dich']}/{rel}\t{why}")
                by_rule[why.split("@")[0]] = by_rule.get(why.split("@")[0], 0) + 1
            entry["chan_theo_luat"] = by_rule

            if scan.allowed:
                list_file = log_dir / f"files-from-{item['dich']}.txt"
                list_file.write_text("\n".join(scan.allowed) + "\n", encoding="utf-8")
                log_file = log_dir / f"rclone-{item['dich']}-{stamp}.log"
                cmd = build_rclone_cmd(cfg, str(src), item["dich"], list_file, log_file, chay_that=chay_that)
                try:
                    proc = runner(cmd, capture_output=True, text=True, timeout=3600)
                    entry["rclone_ma"] = proc.returncode
                    if proc.returncode != 0:
                        status["loi"].append(f"rclone '{item['dich']}' mã {proc.returncode}")
                except FileNotFoundError:
                    entry["rclone_ma"] = -1
                    status["loi"].append("Không tìm thấy rclone (kiểm đường dẫn 'rclone' trong cấu hình)")
                except subprocess.TimeoutExpired:
                    entry["rclone_ma"] = -2
                    status["loi"].append(f"rclone '{item['dich']}' quá thời gian")
            else:
                entry["rclone_ma"] = 0
            status["thu_muc"].append(entry)

        if chan_lines:
            (log_dir / f"chan-{stamp}.txt").write_text("\n".join(chan_lines) + "\n", encoding="utf-8")

        if status["loi"]:
            status["ket_qua"] = "loi"
        elif chay_that:
            status["lan_thanh_cong_cuoi"] = status["ts"]
        _write_json_atomic(status_path, status)

        if chay_that and status["ket_qua"] == "ok":
            try:  # file trạng thái nhỏ để Claude/Chuông đọc nhanh
                runner([cfg["rclone"], "copyto", str(status_path), f"{cfg['remote']}{STATUS_NAME}"],
                       capture_output=True, text=True, timeout=300)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    return status


def kiem_tuoi(cfg: dict[str, Any], *, now: float | None = None) -> tuple[bool, str]:
    """True nếu còn trong hạn. Quá hạn thì ghi 1 tin cảnh báo (tối đa 1 lần/24 giờ) nếu cấu hình thu_muc_tin."""
    now_ts = now if now is not None else time.time()
    log_dir = Path(cfg["thu_muc_log"])
    status_path = log_dir / STATUS_NAME
    last = None
    if status_path.is_file():
        try:
            last = json.loads(status_path.read_text(encoding="utf-8")).get("lan_thanh_cong_cuoi")
        except (OSError, json.JSONDecodeError):
            last = None
    limit_s = float(cfg["bao_loi_sau_gio"]) * 3600
    if last:
        age = now_ts - datetime.fromisoformat(last).timestamp()
        if age <= limit_s:
            return True, f"Lần đẩy thành công cuối: {last}"
        msg = f"Quá {cfg['bao_loi_sau_gio']} giờ chưa đẩy được lên Drive (lần cuối {last})"
    else:
        msg = "Chưa có lần đẩy thành công nào lên Drive"

    tin_dir = cfg.get("thu_muc_tin")
    if tin_dir and Path(tin_dir).is_dir():
        alert_state = log_dir / "canh-bao.json"
        last_alert = 0.0
        if alert_state.is_file():
            try:
                last_alert = float(json.loads(alert_state.read_text(encoding="utf-8")).get("ts", 0))
            except (OSError, ValueError):
                last_alert = 0.0
        if now_ts - last_alert > 24 * 3600:
            when = _now_vn(now_ts)
            name = f"tin-{when.strftime('%Y-%m-%dT%H-%M')}__viec__dong-bo-drive-loi.json"
            tin = {
                "id": name[:-5], "ts": when.isoformat(timespec="seconds"), "type": "viec",
                "tags": ["dong-bo-drive", "canh-bao"], "from": "DongBoDrive", "to": ["CC-QLVIP"],
                "chu_de": "dong-bo-drive-loi", "ack_status": "sent", "can_xac_nhan": False,
                "noiDung": [msg + ". Xem trang-thai-dong-bo.json và nhật ký rclone trong thư mục log."],
            }
            _write_json_atomic(Path(tin_dir) / name, tin)
            _write_json_atomic(alert_state, {"ts": now_ts})
    return False, msg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--chay-that", action="store_true", help="ghi lên Drive (mặc định chỉ chạy thử)")
    ap.add_argument("--kiem-tuoi", action="store_true", help="chỉ kiểm có quá hạn chưa đồng bộ không")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(Path(args.config))
    except ConfigError as exc:
        print(f"LỖI cấu hình: {exc}", file=sys.stderr)
        return 1
    if args.kiem_tuoi:
        ok, msg = kiem_tuoi(cfg)
        print(msg)
        return 0 if ok else 2
    try:
        status = chay_dong_bo(cfg, chay_that=args.chay_that)
    except RuntimeError as exc:
        print(f"BỎ QUA: {exc}", file=sys.stderr)
        return 1
    for e in status["thu_muc"]:
        print(f"{e['dich']}: tìm {e['tim_thay']} · sẽ đẩy {e['se_day']} · chặn {e['bi_chan']} · rclone {e['rclone_ma']}")
    for loi in status["loi"]:
        print("LỖI:", loi, file=sys.stderr)
    print(f"Chế độ: {status['che_do']} · kết quả: {status['ket_qua']}")
    return 0 if status["ket_qua"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
