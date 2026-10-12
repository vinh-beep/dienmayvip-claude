"""QR tại cửa hàng DienmayVIP — học theo kiểu "quét QR tại bàn" của iPOS O2O.

Mỗi tem QR mang sẵn vị trí: ?sku=...&cn=<chi nhánh>&ke=<kệ>&nguon=<tem|poster|standee|wobbler|bh>.
Ba việc:
  (a) Khách xem giá/tồn tại chi nhánh và bấm "Cần tư vấn tại kệ" → báo vào thư mục Chuông.
  (b) QR trên phiếu bảo hành: khách đăng ký nhận tin, CHỈ lưu khi khách tick đồng ý (NĐ 13/2023).
  (c) Mỗi lượt quét ghi nguồn → báo cáo kênh in ấn nào kéo khách.

Luật áp dụng:
  * Giá fail-closed: chỉ hiện giá khi tệp giá live còn tươi (mặc định ≤ 15 phút), không thì "liên hệ".
  * Không bao giờ trả trường giá vốn / giá nhập / NCC; tệp có trường đó thì từ chối khởi động.
  * SĐT khách lưu ở thư mục riêng (không nằm trong vùng đồng bộ Drive), có ghi phiên bản điều khoản + thời điểm.
  * Không gọi AI ở đâu cả — 0 token.

Chạy:  uvicorn app:create_app_from_env --factory --host 127.0.0.1 --port 8770
"""
from __future__ import annotations

import hmac
import json
import os
import re
import threading
import time
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent

CHI_NHANH = {"VV": "Kho tổng", "30LL": "30 Lê Lợi", "BT": "Ba Tri", "TP": "Thạnh Phú", "BD": "Bình Đại"}
NGUON = {"tem", "poster", "standee", "wobbler", "bh", "khac"}
LOAI_SU_KIEN = {"quet", "goi_tu_van"}

TRUONG_CAM_RE = re.compile(
    r"(gia_?von|gia_?nhap|gia_?ncc|gia_?si|ncc|nha_?cung_?cap|supplier|cost|loi_?nhuan|margin|bien_?lai)",
    re.IGNORECASE,
)
SKU_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
KE_RE = re.compile(r"^[A-Za-z0-9-]{1,16}$")
SDT_RE = re.compile(r"^0[35789]\d{8}$")
IMEI_RE = re.compile(r"^\d{15}$")


class CauHinhLoi(ValueError):
    pass


@dataclass(frozen=True)
class CauHinh:
    tep_gia_live: Path          # bản công khai: sku, ten, gia, ton{cn: sl}, (thong_so)
    thu_muc_du_lieu: Path       # su-kien.jsonl
    thu_muc_rieng_tu: Path      # khach-dong-y.jsonl — NGOÀI vùng đồng bộ Drive
    thu_muc_chuong: Path        # mỗi lượt gọi tư vấn = 1 tệp JSON cho Chuông
    token_bao_cao: str
    tuoi_gia_toi_da_giay: int = 15 * 60
    phien_ban_dieu_khoan: str = "DK-2026-10-v1"
    gioi_han_moi_phut: int = 30
    # Phần nội bộ nhân viên (nhan_vien.py): bỏ trống ma_nhan_vien = tắt
    ma_nhan_vien: tuple[str, ...] = ()
    thu_muc_yeu_cau: Path | None = None  # đề nghị chuyển kho / đặt NCC, chờ anh duyệt
    nguong_sap_het: int = 2
    nguong_ton_lon: int = 30


def _kiem_khong_trong_vung_sync(p: Path, ten: str) -> None:
    s = str(p).lower().replace("\\", "/")
    if "my drive" in s or "dmv-cloud-bridge" in s or "dmv_sync" in s:
        raise CauHinhLoi(f"{ten} không được nằm trong vùng đồng bộ Drive: {p}")


def cau_hinh_tu_env() -> CauHinh:
    def bat_buoc(k: str) -> str:
        v = os.environ.get(k, "").strip()
        if not v:
            raise CauHinhLoi(f"Thiếu biến môi trường {k}")
        return v

    token = bat_buoc("QR_TOKEN_BAO_CAO")
    if len(token) < 32:
        raise CauHinhLoi("QR_TOKEN_BAO_CAO phải dài ít nhất 32 ký tự")
    ch = CauHinh(
        tep_gia_live=Path(bat_buoc("QR_TEP_GIA_LIVE")),
        thu_muc_du_lieu=Path(bat_buoc("QR_THU_MUC_DU_LIEU")),
        thu_muc_rieng_tu=Path(bat_buoc("QR_THU_MUC_RIENG_TU")),
        thu_muc_chuong=Path(bat_buoc("QR_THU_MUC_CHUONG")),
        token_bao_cao=token,
        tuoi_gia_toi_da_giay=int(os.environ.get("QR_TUOI_GIA_TOI_DA_GIAY", 900)),
        ma_nhan_vien=tuple(m.strip() for m in os.environ.get("QR_MA_NHAN_VIEN", "").split(",") if m.strip()),
        thu_muc_yeu_cau=Path(os.environ["QR_THU_MUC_YEU_CAU"]) if os.environ.get("QR_THU_MUC_YEU_CAU") else None,
        nguong_sap_het=int(os.environ.get("QR_NGUONG_SAP_HET", 2)),
        nguong_ton_lon=int(os.environ.get("QR_NGUONG_TON_LON", 30)),
    )
    if any(len(m) < 8 for m in ch.ma_nhan_vien):
        raise CauHinhLoi("Mỗi mã nhân viên trong QR_MA_NHAN_VIEN phải dài ít nhất 8 ký tự")
    if ch.ma_nhan_vien and ch.thu_muc_yeu_cau is None:
        raise CauHinhLoi("Bật mã nhân viên thì phải có QR_THU_MUC_YEU_CAU")
    _kiem_khong_trong_vung_sync(ch.thu_muc_rieng_tu, "QR_THU_MUC_RIENG_TU")
    return ch


GIO_VN = timezone(timedelta(hours=7))


def _gio_vn() -> str:
    return datetime.now(GIO_VN).isoformat(timespec="seconds")


def _ghi_dong(tep: Path, ban_ghi: dict[str, Any], khoa: threading.Lock) -> None:
    tep.parent.mkdir(parents=True, exist_ok=True)
    with khoa, tep.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")


class KhoGia:
    """Đọc tệp giá live, bỏ cache khi tệp đổi. Fail-closed khi cũ hoặc lỗi."""

    def __init__(self, tep: Path, tuoi_toi_da: int):
        self.tep, self.tuoi_toi_da = tep, tuoi_toi_da
        self._mtime: float | None = None
        self._du_lieu: dict[str, dict[str, Any]] = {}
        self._khoa = threading.Lock()

    def _nap(self) -> None:
        mtime = self.tep.stat().st_mtime
        if mtime == self._mtime:
            return
        raw = json.loads(self.tep.read_text(encoding="utf-8"))
        items = raw["san_pham"] if isinstance(raw, dict) else raw
        du_lieu: dict[str, dict[str, Any]] = {}
        for sp in items:
            cam = [k for k in sp if TRUONG_CAM_RE.search(k)]
            if cam:
                # tệp công khai lẫn trường nội bộ → từ chối cả tệp
                raise CauHinhLoi(f"Tệp giá live có trường cấm: {cam}")
            du_lieu[str(sp["sku"])] = sp
        self._du_lieu, self._mtime = du_lieu, mtime

    def lay(self, sku: str) -> tuple[dict[str, Any] | None, bool]:
        """Trả (sản phẩm, giá_tươi). Sản phẩm None nếu không có / không đọc được."""
        with self._khoa:
            try:
                self._nap()
            except (OSError, ValueError, KeyError):
                return None, False
            tuoi = time.time() - (self._mtime or 0)
            return self._du_lieu.get(sku), tuoi <= self.tuoi_toi_da

    def tat_ca(self) -> list[dict[str, Any]]:
        with self._khoa:
            try:
                self._nap()
            except (OSError, ValueError, KeyError):
                return []
            return list(self._du_lieu.values())


class GioiHanLuot:
    def __init__(self, moi_phut: int):
        self.moi_phut = moi_phut
        self._lich: dict[str, deque[float]] = defaultdict(deque)
        self._khoa = threading.Lock()

    def cho_phep(self, ip: str) -> bool:
        now = time.monotonic()
        with self._khoa:
            q = self._lich[ip]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.moi_phut:
                return False
            q.append(now)
            return True


class SuKien(BaseModel):
    loai: str
    sku: str
    cn: str
    ke: str = ""
    nguon: str = "khac"


class DangKy(BaseModel):
    sdt: str
    dong_y: bool
    imei: str = ""
    sku: str = ""
    cn: str = ""
    nguon: str = "bh"


class HuyDangKy(BaseModel):
    sdt: str


def _chuan_vi_tri(sku: str, cn: str, ke: str, nguon: str) -> tuple[str, str, str, str]:
    if not SKU_RE.match(sku):
        raise HTTPException(400, "sku không hợp lệ")
    if cn not in CHI_NHANH:
        raise HTTPException(400, "chi nhánh không hợp lệ")
    if ke and not KE_RE.match(ke):
        raise HTTPException(400, "kệ không hợp lệ")
    return sku, cn, ke, nguon if nguon in NGUON else "khac"


def create_app(ch: CauHinh) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    kho = KhoGia(ch.tep_gia_live, ch.tuoi_gia_toi_da_giay)
    gioi_han = GioiHanLuot(ch.gioi_han_moi_phut)
    khoa_su_kien, khoa_rieng_tu = threading.Lock(), threading.Lock()
    tep_su_kien = ch.thu_muc_du_lieu / "su-kien.jsonl"
    tep_dong_y = ch.thu_muc_rieng_tu / "khach-dong-y.jsonl"

    def chan_spam(req: Request) -> None:
        if not gioi_han.cho_phep(req.client.host if req.client else "?"):
            raise HTTPException(429, "Thao tác quá nhanh, thử lại sau 1 phút")

    @app.get("/")
    def trang() -> FileResponse:
        return FileResponse(HERE / "trang.html", media_type="text/html; charset=utf-8")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/sp/{sku}")
    def san_pham(sku: str, cn: str = "30LL") -> dict[str, Any]:
        if not SKU_RE.match(sku) or cn not in CHI_NHANH:
            raise HTTPException(400, "tham số không hợp lệ")
        sp, tuoi = kho.lay(sku)
        if sp is None:
            raise HTTPException(404, "Không tìm thấy sản phẩm")
        ton = sp.get("ton") or {}
        return {
            "sku": sku,
            "ten": sp.get("ten", ""),
            "thong_so": sp.get("thong_so", []),
            "gia": sp.get("gia") if tuoi else None,  # fail-closed
            "gia_trang_thai": "live" if tuoi else "lien_he",
            "chi_nhanh": CHI_NHANH[cn],
            "con_hang_tai_day": int(ton.get(cn, 0) or 0) > 0,
            "con_hang_noi_khac": [CHI_NHANH[k] for k, v in ton.items() if k != cn and k in CHI_NHANH and int(v or 0) > 0],
        }

    @app.post("/su-kien")
    def su_kien(body: SuKien, req: Request) -> dict[str, str]:
        chan_spam(req)
        if body.loai not in LOAI_SU_KIEN:
            raise HTTPException(400, "loại không hợp lệ")
        sku, cn, ke, nguon = _chuan_vi_tri(body.sku, body.cn, body.ke, body.nguon)
        rec = {"id": uuid.uuid4().hex[:12], "luc": _gio_vn(), "loai": body.loai,
               "sku": sku, "cn": cn, "ke": ke, "nguon": nguon}
        _ghi_dong(tep_su_kien, rec, khoa_su_kien)
        if body.loai == "goi_tu_van":
            sp, _ = kho.lay(sku)
            tin = {**rec, "ten_sp": (sp or {}).get("ten", sku), "chi_nhanh": CHI_NHANH[cn],
                   "noi_dung": f"Khách cần tư vấn tại kệ {ke or '?'} — {CHI_NHANH[cn]}"}
            ch.thu_muc_chuong.mkdir(parents=True, exist_ok=True)
            tam = ch.thu_muc_chuong / f".{rec['id']}.tmp"
            tam.write_text(json.dumps(tin, ensure_ascii=False), encoding="utf-8")
            tam.replace(ch.thu_muc_chuong / f"qr-tu-van-{rec['id']}.json")  # ghi nguyên tử
        return {"ok": "1"}

    @app.post("/dang-ky")
    def dang_ky(body: DangKy, req: Request) -> dict[str, str]:
        chan_spam(req)
        if body.dong_y is not True:
            raise HTTPException(400, "Cần khách đồng ý mới lưu")
        if not SDT_RE.match(body.sdt):
            raise HTTPException(400, "Số điện thoại không hợp lệ")
        if body.imei and not IMEI_RE.match(body.imei):
            raise HTTPException(400, "IMEI không hợp lệ")
        if body.cn and body.cn not in CHI_NHANH:
            raise HTTPException(400, "chi nhánh không hợp lệ")
        _ghi_dong(tep_dong_y, {"luc": _gio_vn(), "hanh_dong": "dong_y", "sdt": body.sdt, "imei": body.imei,
                               "sku": body.sku[:64], "cn": body.cn, "dieu_khoan": ch.phien_ban_dieu_khoan},
                  khoa_rieng_tu)
        # sự kiện đếm KHÔNG chứa SĐT
        _ghi_dong(tep_su_kien, {"id": uuid.uuid4().hex[:12], "luc": _gio_vn(), "loai": "dang_ky",
                                "sku": body.sku[:64], "cn": body.cn,
                                "ke": "", "nguon": body.nguon if body.nguon in NGUON else "khac"}, khoa_su_kien)
        return {"ok": "1"}

    @app.post("/huy-dang-ky")
    def huy_dang_ky(body: HuyDangKy, req: Request) -> dict[str, str]:
        chan_spam(req)
        if not SDT_RE.match(body.sdt):
            raise HTTPException(400, "Số điện thoại không hợp lệ")
        _ghi_dong(tep_dong_y, {"luc": _gio_vn(), "hanh_dong": "rut_dong_y", "sdt": body.sdt}, khoa_rieng_tu)
        return {"ok": "1"}

    @app.get("/bao-cao")
    def bao_cao(req: Request) -> JSONResponse:
        auth = req.headers.get("authorization", "")
        if not hmac.compare_digest(auth.encode(), f"Bearer {ch.token_bao_cao}".encode()):
            raise HTTPException(401, "Sai token")
        dem: dict[str, Counter] = {k: Counter() for k in ("loai", "nguon", "cn", "sku", "nguon_loai")}
        if tep_su_kien.exists():
            for dong in tep_su_kien.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(dong)
                except ValueError:
                    continue
                for k in ("loai", "nguon", "cn", "sku"):
                    dem[k][r.get(k, "")] += 1
                dem["nguon_loai"][f"{r.get('nguon')}:{r.get('loai')}"] += 1
        return JSONResponse({k: dict(v.most_common(50)) for k, v in dem.items()})

    if ch.ma_nhan_vien:
        from nhan_vien import gan_route_nhan_vien
        gan_route_nhan_vien(app, ch, kho, chan_spam)
    return app


def create_app_from_env() -> FastAPI:
    return create_app(cau_hinh_tu_env())
