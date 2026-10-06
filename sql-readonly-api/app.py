"""API chỉ-đọc DienmayVIP — chạy trên máy SQL Server, Claude Cloud đọc qua HTTPS.

Nguyên tắc:
  * Không có SQL tùy ý: chỉ đọc các view đã khai báo trong views.json (tên phải bắt đầu vw_API_).
  * Cột phải liệt kê rõ; cột nghi giá vốn / NCC / mật khẩu / SĐT bị chặn ngay khi khởi động.
  * Mọi giá trị lọc đều đi qua tham số (?), không ghép chuỗi.
  * Token Bearer dài, so sánh hằng thời gian; sai nhiều lần thì khóa tạm.
  * Không gọi AI/LLM ở bất kỳ đâu — xử lý thuần mã, 0 token.

Chạy:  uvicorn app:create_app_from_env --factory --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- cấu hình view

IDENT_RE = re.compile(r"^[^\W\d]\w*$")
VIEW_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SOURCE_PREFIX = "vw_API_"
BLOCKED_COLUMN_RE = re.compile(
    r"(gia_?von|gia_?nhap|don_?gia_?nhap|ncc|nha_?cung_?cap|supplier|cost|"
    r"mat_?khau|password|passwd|token|secret|api_?key|sdt|so_?dien_?thoai|dien_?thoai|phone|email)",
    re.IGNORECASE,
)
DEFAULT_LIMIT = 50  # trang nhỏ để mỗi lần Claude đọc tốn ít token


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ViewSpec:
    name: str
    source: str
    columns: tuple[str, ...]
    filter_columns: tuple[str, ...]
    order_by: str
    max_rows: int
    description: str


def _check_ident(value: Any, what: str) -> str:
    if not isinstance(value, str) or not IDENT_RE.match(value):
        raise ConfigError(f"{what} không hợp lệ: {value!r}")
    return value


def parse_views(raw: dict[str, Any]) -> dict[str, ViewSpec]:
    views_raw = raw.get("views")
    if not isinstance(views_raw, dict) or not views_raw:
        raise ConfigError("views.json phải có mục 'views' không rỗng")
    result: dict[str, ViewSpec] = {}
    for name, item in views_raw.items():
        if not VIEW_NAME_RE.match(name):
            raise ConfigError(f"Tên view API không hợp lệ: {name!r} (chỉ a-z, 0-9, dấu gạch)")
        source = item.get("source")
        if not isinstance(source, str):
            raise ConfigError(f"[{name}] thiếu 'source'")
        parts = source.split(".")
        if len(parts) > 2:
            raise ConfigError(f"[{name}] source chỉ dạng schema.view hoặc view: {source!r}")
        for p in parts:
            _check_ident(p, f"[{name}] source")
        if not parts[-1].startswith(SOURCE_PREFIX):
            raise ConfigError(f"[{name}] source phải là view bắt đầu bằng {SOURCE_PREFIX} (không mở bảng gốc)")
        columns = item.get("columns")
        if not isinstance(columns, list) or not columns or len(set(columns)) != len(columns):
            raise ConfigError(f"[{name}] 'columns' phải là danh sách không rỗng, không trùng")
        for c in columns:
            _check_ident(c, f"[{name}] cột")
            if BLOCKED_COLUMN_RE.search(c):
                raise ConfigError(f"[{name}] cột {c!r} thuộc nhóm bị chặn (giá vốn/NCC/bí mật/SĐT)")
        filters = item.get("filter_columns", [])
        if not isinstance(filters, list) or not set(filters) <= set(columns):
            raise ConfigError(f"[{name}] 'filter_columns' phải là tập con của 'columns'")
        order_by = item.get("order_by")
        if order_by not in columns:
            raise ConfigError(f"[{name}] 'order_by' phải là một cột trong 'columns'")
        max_rows = item.get("max_rows", 1000)
        if not isinstance(max_rows, int) or isinstance(max_rows, bool) or not 1 <= max_rows <= 5000:
            raise ConfigError(f"[{name}] 'max_rows' phải từ 1 đến 5000")
        result[name] = ViewSpec(
            name=name,
            source=source,
            columns=tuple(columns),
            filter_columns=tuple(filters),
            order_by=order_by,
            max_rows=max_rows,
            description=str(item.get("description", "")),
        )
    return result


def load_views(path: Path) -> dict[str, ViewSpec]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Không đọc được {path}: {exc}") from exc
    return parse_views(raw)


# ---------------------------------------------------------------- dựng câu SELECT


def _q(ident: str) -> str:
    return f"[{ident}]"


def _quote_source(source: str) -> str:
    return ".".join(_q(p) for p in source.split("."))


def build_select(
    spec: ViewSpec, dialect: str, filters: dict[str, str], limit: int, offset: int
) -> tuple[str, list[Any]]:
    """Lấy limit+1 dòng để biết còn trang sau hay không. Chỉ định danh đã kiểm tra được ghép vào chuỗi."""
    cols = ", ".join(_q(c) for c in spec.columns)
    where = ""
    params: list[Any] = []
    if filters:
        where = " WHERE " + " AND ".join(f"{_q(c)} = ?" for c in filters)
        params.extend(filters.values())
    base = f"SELECT {cols} FROM {_quote_source(spec.source)}{where} ORDER BY {_q(spec.order_by)}"
    if dialect == "sqlserver":
        return base + " OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", params + [offset, limit + 1]
    if dialect == "sqlite":  # dùng cho kiểm thử
        return base + " LIMIT ? OFFSET ?", params + [limit + 1, offset]
    raise ValueError(f"dialect không hỗ trợ: {dialect}")


# ---------------------------------------------------------------- backend DB


def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def pick_driver(available: list[str]) -> str:
    for wanted in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "ODBC Driver 13 for SQL Server"):
        if wanted in available:
            return wanted
    raise RuntimeError("Chưa cài ODBC Driver 17/18 for SQL Server")


class SqlServerBackend:
    dialect = "sqlserver"

    def __init__(self, server: str, database: str, user: str, password: str, timeout: int = 15):
        import pyodbc  # chỉ cần khi chạy thật

        driver = pick_driver(list(pyodbc.drivers()))
        self.timeout = timeout
        self._conn_str = (
            f"DRIVER={_odbc_value(driver)};SERVER={_odbc_value(server)};DATABASE={_odbc_value(database)};"
            f"UID={_odbc_value(user)};PWD={_odbc_value(password)};"
            "Encrypt=no;TrustServerCertificate=yes;ApplicationIntent=ReadOnly"
        )

    def query(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        import pyodbc

        conn = pyodbc.connect(self._conn_str, timeout=self.timeout, autocommit=True)
        try:
            conn.timeout = self.timeout
            cur = conn.cursor()
            cur.execute(sql, params)
            return _rows_to_dicts(cur)
        finally:
            conn.close()


def ensure_least_privilege(backend) -> None:
    """Từ chối chạy nếu tài khoản SQL có quyền ghi/quản trị — API chỉ-đọc phải dùng login chỉ SELECT."""
    rows = backend.query(
        "SELECT CAST(IS_SRVROLEMEMBER('sysadmin') AS int) AS sysadmin, "
        "CAST(IS_MEMBER('db_owner') AS int) AS db_owner, "
        "CAST(IS_MEMBER('db_datawriter') AS int) AS db_datawriter, "
        "CAST(IS_MEMBER('db_ddladmin') AS int) AS db_ddladmin",
        [],
    )
    flags = rows[0] if rows else {}
    risky = [k for k, v in flags.items() if v == 1]
    if risky:
        raise RuntimeError(
            "Tài khoản SQL của API đang có quyền " + ", ".join(risky) + ". Dùng login chỉ SELECT (xem cap-quyen.sql.example)."
        )


# ---------------------------------------------------------------- giới hạn tần suất


class SlidingWindow:
    def __init__(self, limit: int, window_s: float, clock=time.monotonic):
        self.limit, self.window_s, self._clock = limit, window_s, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque[float]:
        q = self._events[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._trim(key, self._clock())) >= self.limit

    def record(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._trim(key, now).append(now)

    def allow(self, key: str) -> bool:
        with self._lock:
            now = self._clock()
            q = self._trim(key, now)
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


# ---------------------------------------------------------------- ứng dụng


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else "?"


def _audit_logger(path: Path | None) -> logging.Logger:
    logger = logging.getLogger("dmv.api.audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if path is not None and not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


def create_app(
    *,
    token: str,
    views: dict[str, ViewSpec],
    backend,
    audit_path: Path | None = None,
    requests_per_minute: int = 120,
) -> FastAPI:
    if len(token) < 32:
        raise ConfigError("DMV_API_TOKEN phải dài ít nhất 32 ký tự")
    token_bytes = token.encode()
    audit = _audit_logger(audit_path)
    failures = SlidingWindow(limit=10, window_s=300)
    limiter = SlidingWindow(limit=requests_per_minute, window_s=60)

    app = FastAPI(title="DMV API chỉ-đọc", docs_url=None, redoc_url=None, openapi_url=None)

    def log(event: str, ip: str, **extra: Any) -> None:
        audit.info(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "event": event, "ip": ip, **extra}, ensure_ascii=False))

    def require_token(request: Request) -> None:
        ip = _client_ip(request)
        if failures.blocked(ip):
            raise HTTPException(429, "Thử sai quá nhiều lần, đợi vài phút rồi thử lại")
        scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(supplied.strip().encode(), token_bytes):
            failures.record(ip)
            log("auth_fail", ip, path=request.url.path)
            raise HTTPException(401, "Thiếu hoặc sai token", headers={"WWW-Authenticate": "Bearer"})
        if not limiter.allow("all"):
            raise HTTPException(429, "Quá số lượt gọi cho phép mỗi phút")

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/v1/views", dependencies=[Depends(require_token)])
    def list_views() -> dict[str, Any]:
        return {
            "views": [
                {
                    "name": v.name,
                    "description": v.description,
                    "columns": list(v.columns),
                    "filter_columns": list(v.filter_columns),
                    "max_rows": v.max_rows,
                }
                for v in views.values()
            ]
        }

    @app.get("/v1/views/{name}", dependencies=[Depends(require_token)])
    def get_view(name: str, request: Request):
        ip = _client_ip(request)
        spec = views.get(name)
        if spec is None:
            raise HTTPException(404, "Không có view này")
        query = dict(request.query_params)
        try:
            limit = int(query.pop("limit", min(DEFAULT_LIMIT, spec.max_rows)))
            offset = int(query.pop("offset", 0))
        except ValueError:
            raise HTTPException(400, "limit và offset phải là số nguyên")
        if offset < 0 or limit < 1:
            raise HTTPException(400, "limit phải ≥ 1 và offset ≥ 0")
        limit = min(limit, spec.max_rows)
        unknown = [k for k in query if k not in spec.filter_columns]
        if unknown:
            raise HTTPException(400, f"Không được lọc theo {unknown}. Cho phép: {list(spec.filter_columns)}")

        sql, params = build_select(spec, backend.dialect, query, limit, offset)
        started = time.monotonic()
        try:
            rows = backend.query(sql, params)
        except Exception:  # không trả chi tiết lỗi SQL ra ngoài
            logging.getLogger("dmv.api").exception("Lỗi truy vấn view %s", name)
            log("db_error", ip, view=name)
            raise HTTPException(502, "Lỗi đọc dữ liệu, xem log trên máy chủ")
        has_more = len(rows) > limit
        rows = rows[:limit]
        log("read", ip, view=name, rows=len(rows), filters=sorted(query), ms=int((time.monotonic() - started) * 1000))
        return JSONResponse(
            jsonable_encoder(
                {
                    "view": name,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "limit": limit,
                    "offset": offset,
                    "count": len(rows),
                    "has_more": has_more,
                    "rows": rows,
                }
            )
        )

    return app


# ---------------------------------------------------------------- khởi động từ môi trường


def load_env_file(path: Path) -> None:
    """Đọc config.env dạng KEY=VALUE (không ghi đè biến môi trường đã có)."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def create_app_from_env() -> FastAPI:
    load_env_file(HERE / "config.env")
    required = ["DMV_API_TOKEN", "DMV_SQL_SERVER", "DMV_SQL_DATABASE", "DMV_SQL_USER", "DMV_SQL_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise ConfigError("Thiếu cấu hình: " + ", ".join(missing))
    views = load_views(Path(os.environ.get("DMV_VIEWS_FILE", HERE / "views.json")))
    backend = SqlServerBackend(
        os.environ["DMV_SQL_SERVER"], os.environ["DMV_SQL_DATABASE"], os.environ["DMV_SQL_USER"], os.environ["DMV_SQL_PASSWORD"]
    )
    ensure_least_privilege(backend)
    return create_app(
        token=os.environ["DMV_API_TOKEN"],
        views=views,
        backend=backend,
        audit_path=Path(os.environ.get("DMV_AUDIT_LOG", HERE / "api-audit.log")),
        requests_per_minute=int(os.environ.get("DMV_RATE_PER_MIN", "120")),
    )
