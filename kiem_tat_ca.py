"""Khung kiểm thử cho cả kho (không gọi AI, 0 token, chỉ thư viện chuẩn + pytest).

  python kiem_tat_ca.py             # chạy bộ kiểm của từng thư mục con, báo bảng kết quả
  python kiem_tat_ca.py --tu-kiem   # kiểm tra CHÍNH bộ kiểm: cố ý phá mã, bộ kiểm phải báo đỏ

--tu-kiem (kiểu "đột biến"): chép mỗi thư mục ra thư mục tạm, sửa đúng 1 chỗ quan trọng
(tắt xác thực, tắt chặn cột giá vốn, đổi copy thành sync...), chạy lại bộ kiểm.
Bộ kiểm tốt phải ĐỎ. Đột biến nào bộ kiểm vẫn xanh = lỗ hổng trong bộ kiểm → mã thoát 1.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUITES = ["sql-readonly-api", "drive-sync"]

# (thư mục, tệp, đoạn gốc, đoạn thay, ý nghĩa). Đoạn gốc PHẢI xuất hiện đúng 1 lần.
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("sql-readonly-api", "app.py",
     'if scheme.lower() != "bearer" or not hmac.compare_digest(supplied.strip().encode(), token_bytes):',
     "if False:", "tắt kiểm token"),
    ("sql-readonly-api", "app.py", "if BLOCKED_COLUMN_RE.search(c):", "if False:", "tắt chặn cột giá vốn/NCC/bí mật"),
    ("sql-readonly-api", "app.py", "if not parts[-1].startswith(SOURCE_PREFIX):", "if False:", "cho mở bảng gốc (không cần vw_API_)"),
    ("sql-readonly-api", "app.py", "limit = min(limit, spec.max_rows)", "limit = limit", "bỏ trần số dòng"),
    ("sql-readonly-api", "app.py", "if unknown:", "if False:", "cho lọc theo cột bất kỳ"),
    ("sql-readonly-api", "app.py", "if risky:", "if False:", "cho chạy với tài khoản có quyền ghi"),
    ("sql-readonly-api", "app.py", "failures.record(ip)", "pass", "tắt khóa tạm khi sai token nhiều lần"),
    ("drive-sync", "kiem_an_toan.py", "if ten_bi_chan(fn):", "if False:", "tắt chặn tệp tên nhạy cảm"),
    ("drive-sync", "kiem_an_toan.py", "if d.lower() in EXCLUDE_DIRS:", "if False:", "đẩy cả venv/site-packages/torch"),
    ("drive-sync", "kiem_an_toan.py", "if st.st_size > max_size:", "if False:", "bỏ giới hạn dung lượng"),
    ("drive-sync", "dong_bo_drive.py", 'cfg["rclone"], "copy", src,', 'cfg["rclone"], "sync", src,', "đổi copy thành sync (có thể xóa trên Drive)"),
    ("drive-sync", "dong_bo_drive.py", "elif chay_that:\n            status", "else:\n            status", "chạy thử cũng ghi mốc thành công"),
    ("drive-sync", "dong_bo_drive.py", 'elif chay_that and cfg["xac_minh"]:', "elif False:", "bỏ bước đọc lại Drive"),
    ("drive-sync", "kiem_an_toan.py", "verdict.rule in LUAT_MEM and rel in cho_phep_tep",
     "rel in cho_phep_tep", "Harness² vòng 2 nới cả luật cứng (bí mật/giá vốn qua nhờ phán oan)"),
    ("drive-sync", "kiem_an_toan.py", "and bam_tep(Path(full)) == cho_phep_tep[rel]", "",
     "bỏ so SHA-256: tệp phán oan qua dù nội dung đã đổi"),
]


def run_pytest(cwd: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, "-I", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
        cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", timeout=600, env=env,
    )
    tail = (proc.stdout.strip().splitlines() or [proc.stderr.strip()[-200:]])[-1]
    return proc.returncode, tail


def chay_bo_kiem() -> int:
    bad = 0
    for name in SUITES:
        rc, tail = run_pytest(ROOT / name)
        print(f"{'ĐẠT ' if rc == 0 else 'HỎNG'}  {name:18s} {tail}")
        bad += rc != 0
    return 1 if bad else 0


def tu_kiem() -> int:
    survivors = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (folder, fname, old, new, meaning) in enumerate(MUTATIONS):
            work = Path(tmp) / f"m{i}"
            shutil.copytree(ROOT / folder, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))
            target = work / fname
            text = target.read_text(encoding="utf-8")
            if text.count(old) != 1:
                print(f"LỖI  [{folder}/{fname}] đoạn gốc xuất hiện {text.count(old)} lần (phải đúng 1): {meaning}")
                survivors += 1
                continue
            target.write_text(text.replace(old, new), encoding="utf-8")
            rc, tail = run_pytest(work)
            if rc != 0 and "failed" not in tail:  # vỡ cú pháp/nạp mô-đun không tính là "bắt được"
                survivors += 1
                print(f"LỖI  [{folder}/{fname}] {meaning}: đột biến làm vỡ mã thay vì làm ca kiểm đỏ ({tail})")
            elif rc == 0:
                survivors += 1
                print(f"SÓT  [{folder}/{fname}] {meaning}: bộ kiểm vẫn xanh → thiếu ca kiểm")
            else:
                print(f"BẮT  [{folder}/{fname}] {meaning}")
    total = len(MUTATIONS)
    print(f"\nTự kiểm: bắt {total - survivors}/{total} lỗi cố ý")
    return 1 if survivors else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):  # console Windows cp1252 không in được tiếng Việt
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    sys.exit(tu_kiem() if "--tu-kiem" in sys.argv[1:] else chay_bo_kiem())
