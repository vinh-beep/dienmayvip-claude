"""Kiểm API chỉ-đọc TRƯỚC khi mở ra ngoài. Không ghi gì, không gọi AI (0 token).

  python kiem_ket_noi.py --nhe   # chỉ đọc cấu hình + views.json, KHÔNG đụng SQL
  python kiem_ket_noi.py         # đầy đủ: thêm kết nối SQL thật, kiểm quyền, đọc thử từng view

Nguyên tắc "kiểm = đọc lại ĐÍCH, không tin log": mỗi view được đọc thật 1 dòng bằng kết nối mới
và so khớp tên cột với views.json. Mã thoát: 0 đạt · 1 có mục hỏng.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app as api  # noqa: E402

Result = tuple[bool, str]


def kiem_nhe(env: dict[str, str], views_path: Path) -> tuple[list[Result], dict[str, api.ViewSpec]]:
    out: list[Result] = []
    token = env.get("DMV_API_TOKEN", "")
    out.append((len(token) >= 32, "DMV_API_TOKEN dài ≥ 32 ký tự" if len(token) >= 32
                else "DMV_API_TOKEN thiếu hoặc ngắn hơn 32 ký tự"))
    for key in ("DMV_SQL_SERVER", "DMV_SQL_DATABASE", "DMV_SQL_USER", "DMV_SQL_PASSWORD"):
        out.append((bool(env.get(key)), f"{key} {'có' if env.get(key) else 'THIẾU'}"))
    views: dict[str, api.ViewSpec] = {}
    try:
        views = api.load_views(views_path)
        out.append((True, f"views.json hợp lệ ({len(views)} view: {', '.join(views)})"))
    except api.ConfigError as exc:
        out.append((False, f"views.json lỗi: {exc}"))
    return out, views


def kiem_day_du(views: dict[str, api.ViewSpec], backend: Any) -> list[Result]:
    out: list[Result] = []
    try:
        api.ensure_least_privilege(backend)
        out.append((True, "Tài khoản SQL không có quyền ghi/quản trị"))
    except Exception as exc:  # noqa: BLE001 — in lý do ngắn, không in chi tiết kết nối
        out.append((False, f"Kiểm quyền: {exc.__class__.__name__}: {str(exc)[:160]}"))
    for name, spec in views.items():
        sql, params = api.build_select(spec, backend.dialect, {}, 1, 0)
        try:
            rows = backend.query(sql, params)
        except Exception as exc:  # noqa: BLE001
            out.append((False, f"[{name}] đọc thử lỗi: {exc.__class__.__name__}"))
            continue
        if not rows:
            out.append((True, f"[{name}] đọc được, view đang rỗng (chưa so được cột)"))
            continue
        out.append((True, f"[{name}] đọc được 1 dòng thật, đủ {len(spec.columns)} cột khai trong views.json"))
    return out


def _utf8_console() -> None:
    """Console Windows hay là cp1252/cp437: in tiếng Việt sẽ sập UnicodeEncodeError. Ép UTF-8, ký tự lạ thành '?'."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    argv = sys.argv[1:] if argv is None else argv
    nhe = "--nhe" in argv
    api.load_env_file(api.HERE / "config.env")
    env = dict(os.environ)
    results, views = kiem_nhe(env, Path(env.get("DMV_VIEWS_FILE", api.HERE / "views.json")))
    if not nhe and all(ok for ok, _ in results):
        backend = api.SqlServerBackend(env["DMV_SQL_SERVER"], env["DMV_SQL_DATABASE"], env["DMV_SQL_USER"], env["DMV_SQL_PASSWORD"])
        results += kiem_day_du(views, backend)
    for ok, msg in results:
        print(("ĐẠT  " if ok else "HỎNG ") + msg)
    good = all(ok for ok, _ in results)
    print("KẾT LUẬN:", "ĐẠT" if good else "CHƯA ĐẠT — không mở ra ngoài")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
