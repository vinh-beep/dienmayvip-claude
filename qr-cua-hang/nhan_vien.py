"""Phần nội bộ của tem QR: nhân viên quét cùng tem để xem phân loại tồn và lập đề nghị.

  * Phân loại tồn theo từng kho: HET (0) · SAP_HET (≤ ngưỡng) · DU · TON_LON (≥ ngưỡng lớn → ưu tiên đẩy bán).
  * Đề xuất tự động: hết/sắp hết ở kho này mà kho khác dư → gợi ý chuyển kho; cả hệ thống thấp → gợi ý đặt NCC.
  * Nhân viên bấm → ghi 1 tệp đề nghị (trạng thái "cho_duyet") cho Chuông/HTsoft.
    Không tự lập phiếu chuyển kho, không tự đặt hàng NCC: đặt NCC là chi tiền, anh Vĩnh duyệt.
  * Trang nhân viên KHÔNG có giá nhập, tên NCC hay lợi nhuận — chỉ tồn và số lượng đề nghị.
"""
from __future__ import annotations

import hmac
import json
import uuid
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import CHI_NHANH, HERE, SKU_RE, CauHinh, KhoGia, _gio_vn

LOAI_YEU_CAU = {"chuyen_kho", "dat_ncc"}
NHAN = {"HET": "Hết tại đây", "SAP_HET": "Sắp hết", "DU": "Đủ bán", "TON_LON": "Tồn lớn — ưu tiên đẩy bán"}


def phan_loai(sl: int, nguong_sap_het: int, nguong_ton_lon: int) -> str:
    if sl <= 0:
        return "HET"
    if sl <= nguong_sap_het:
        return "SAP_HET"
    if sl >= nguong_ton_lon:
        return "TON_LON"
    return "DU"


def ton_theo_kho(sp: dict[str, Any]) -> dict[str, int]:
    ton = sp.get("ton") or {}
    return {cn: max(int(ton.get(cn, 0) or 0), 0) for cn in CHI_NHANH}


def de_xuat(sp: dict[str, Any], cn: str, ch: CauHinh) -> list[dict[str, Any]]:
    """Gợi ý cho kho `cn`. Chỉ là gợi ý — nhân viên bấm mới thành đề nghị."""
    ton = ton_theo_kho(sp)
    tai_day = ton[cn]
    if tai_day > ch.nguong_sap_het:
        return []
    can = ch.nguong_sap_het + 1 - tai_day  # đưa về mức "Đủ bán"
    goi_y: list[dict[str, Any]] = []
    # kho khác chỉ được rút phần dư trên ngưỡng sắp hết của chính kho đó
    du = {k: v - (ch.nguong_sap_het + 1) for k, v in ton.items() if k != cn and v > ch.nguong_sap_het + 1}
    if du:
        kho_di = max(du, key=du.get)
        goi_y.append({"loai": "chuyen_kho", "cn_di": kho_di, "cn_den": cn, "so_luong": min(can, du[kho_di]),
                      "ly_do": f"{CHI_NHANH[cn]} còn {tai_day}, {CHI_NHANH[kho_di]} còn {ton[kho_di]}"})
    if sum(ton.values()) <= ch.nguong_sap_het * 2:
        goi_y.append({"loai": "dat_ncc", "cn_den": cn, "so_luong": can,
                      "ly_do": f"Toàn hệ thống chỉ còn {sum(ton.values())}"})
    return goi_y


class YeuCau(BaseModel):
    loai: str
    sku: str
    cn_den: str
    cn_di: str = ""
    so_luong: int
    ghi_chu: str = ""


def gan_route_nhan_vien(app: FastAPI, ch: CauHinh, kho: KhoGia, chan_spam: Callable[[Request], None]) -> None:
    assert ch.thu_muc_yeu_cau is not None

    def xac_thuc(req: Request) -> str:
        ma = req.headers.get("x-ma-nv", "")
        for m in ch.ma_nhan_vien:
            if hmac.compare_digest(ma.encode(), m.encode()):
                return m[:3] + "…"  # chỉ ghi tiền tố, không lưu nguyên mã
        raise HTTPException(401, "Sai mã nhân viên")

    @app.get("/nv")
    def trang_nv() -> FileResponse:
        return FileResponse(HERE / "nhan-vien.html", media_type="text/html; charset=utf-8")

    @app.get("/nv/sp/{sku}")
    def sp_nv(sku: str, req: Request, cn: str = "30LL") -> dict[str, Any]:
        xac_thuc(req)
        if not SKU_RE.match(sku) or cn not in CHI_NHANH:
            raise HTTPException(400, "tham số không hợp lệ")
        sp, _ = kho.lay(sku)
        if sp is None:
            raise HTTPException(404, "Không tìm thấy sản phẩm")
        ton = ton_theo_kho(sp)
        return {
            "sku": sku, "ten": sp.get("ten", ""), "cn": cn, "chi_nhanh": CHI_NHANH[cn],
            "kho": [{"cn": k, "ten": CHI_NHANH[k], "sl": v,
                     "loai": phan_loai(v, ch.nguong_sap_het, ch.nguong_ton_lon),
                     "nhan": NHAN[phan_loai(v, ch.nguong_sap_het, ch.nguong_ton_lon)]} for k, v in ton.items()],
            "tong": sum(ton.values()),
            "de_xuat": de_xuat(sp, cn, ch),
        }

    @app.get("/nv/phan-loai")
    def bang_phan_loai(req: Request, cn: str = "30LL") -> dict[str, Any]:
        xac_thuc(req)
        if cn not in CHI_NHANH:
            raise HTTPException(400, "chi nhánh không hợp lệ")
        nhom: dict[str, list[dict[str, Any]]] = {k: [] for k in NHAN}
        for sp in kho.tat_ca():
            ton = ton_theo_kho(sp)
            if sum(ton.values()) == 0:
                continue
            loai = phan_loai(ton[cn], ch.nguong_sap_het, ch.nguong_ton_lon)
            nhom[loai].append({"sku": sp["sku"], "ten": sp.get("ten", ""), "sl": ton[cn], "tong": sum(ton.values()),
                               "de_xuat": de_xuat(sp, cn, ch)})
        for v in nhom.values():
            v.sort(key=lambda r: -r["sl"])
        return {"cn": cn, "chi_nhanh": CHI_NHANH[cn], "nhom": nhom, "nhan": NHAN}

    @app.post("/nv/yeu-cau")
    def yeu_cau(body: YeuCau, req: Request) -> dict[str, str]:
        chan_spam(req)
        nguoi = xac_thuc(req)
        if body.loai not in LOAI_YEU_CAU:
            raise HTTPException(400, "loại đề nghị không hợp lệ")
        if not SKU_RE.match(body.sku) or body.cn_den not in CHI_NHANH:
            raise HTTPException(400, "tham số không hợp lệ")
        if not 1 <= body.so_luong <= 999:
            raise HTTPException(400, "Số lượng phải từ 1 đến 999")
        sp, _ = kho.lay(body.sku)
        if sp is None:
            raise HTTPException(404, "Không tìm thấy sản phẩm")
        if body.loai == "chuyen_kho":
            if body.cn_di not in CHI_NHANH or body.cn_di == body.cn_den:
                raise HTTPException(400, "Kho chuyển đi không hợp lệ")
            con = ton_theo_kho(sp)[body.cn_di]
            if body.so_luong > con:
                raise HTTPException(400, f"{CHI_NHANH[body.cn_di]} chỉ còn {con}")
        rec = {
            "id": uuid.uuid4().hex[:12], "luc": _gio_vn(), "loai": body.loai, "trang_thai": "cho_duyet",
            "sku": body.sku, "ten_sp": sp.get("ten", body.sku), "so_luong": body.so_luong,
            "cn_den": body.cn_den, "cn_di": body.cn_di if body.loai == "chuyen_kho" else "",
            "ghi_chu": body.ghi_chu[:200], "nguoi_lap": nguoi,
            "noi_dung": (f"Đề nghị chuyển {body.so_luong} {sp.get('ten', body.sku)} từ {CHI_NHANH.get(body.cn_di, '')} "
                         f"về {CHI_NHANH[body.cn_den]}") if body.loai == "chuyen_kho" else
                        f"Đề nghị đặt NCC {body.so_luong} {sp.get('ten', body.sku)} cho {CHI_NHANH[body.cn_den]} — chờ anh duyệt",
        }
        thu_muc = ch.thu_muc_yeu_cau
        thu_muc.mkdir(parents=True, exist_ok=True)
        tam = thu_muc / f".{rec['id']}.tmp"
        tam.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        tam.replace(thu_muc / f"qr-de-nghi-{body.loai}-{rec['id']}.json")
        return {"ok": "1", "id": rec["id"]}
