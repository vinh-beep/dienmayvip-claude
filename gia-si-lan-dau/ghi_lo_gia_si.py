# -*- coding: utf-8 -*-
"""
Ghi lô giá sỉ lần đầu vào HTsoft (dmv_GiaSi + MATHANG.GIABANBUON).

Ba chế độ, theo thứ tự an toàn:
  --kham-pha   : CHỈ ĐỌC. In cấu trúc bảng + tiêu đề file lô để xác nhận ánh xạ cột.
  (mặc định)   : XEM TRƯỚC. Đọc lô, lọc, kiểm chốt an toàn, in bảng. KHÔNG ghi gì.
  --ghi        : GHI THẬT. Chỉ sau khi xem trước xong và người chạy gõ đúng chữ GHI.

An toàn (theo luật HTsoft Safe SQL):
  - Backup 2 bảng trước khi ghi (bak_MATHANG_GIABANBUON_<ngày>, bak_dmv_GiaSi_<ngày>).
  - Một TRANSACTION, đếm dòng, lệch số mong đợi => ROLLBACK.
  - Idempotent: chạy lại chỉ sửa dòng còn lệch, không ghi trùng.
  - Số mã trong lô phải ĐÚNG BẰNG so_ma_mong_doi trong config (mặc định 278), lệch => dừng.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
import zoneinfo

VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
NGUOI_TAO = "AI VIP"


# ----------------------------------------------------------------- tiện ích
def gio_vn():
    return dt.datetime.now(VN)


def ten_file(goc, duoi):
    return f"{goc} {gio_vn().strftime('%d %m %Y %Hh%Mp')}.{duoi}"


def bo_dau(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower().strip()


def doc_config(duong_dan):
    with open(duong_dan, encoding="utf-8-sig") as f:
        return json.load(f)


class Log:
    def __init__(self, thu_muc):
        os.makedirs(thu_muc, exist_ok=True)
        self.duong_dan = os.path.join(thu_muc, ten_file("Log Ghi Lo Gia Si", "txt"))
        self.f = open(self.duong_dan, "a", encoding="utf-8")

    def __call__(self, *phan):
        dong = " ".join(str(p) for p in phan)
        print(dong)
        self.f.write(f"[{gio_vn().strftime('%H:%M:%S')}] {dong}\n")
        self.f.flush()


# ----------------------------------------------------------------- SQL
def ket_noi(cfg):
    import pyodbc

    uu_tien = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]
    co = [d for d in uu_tien if d in pyodbc.drivers()]
    if not co:
        raise SystemExit("Không có ODBC Driver 17/18 for SQL Server.")
    chuoi = (
        f"DRIVER={{{co[0]}}};SERVER={cfg['server']};DATABASE={cfg['database']};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no"
    )
    return pyodbc.connect(chuoi, autocommit=False)


def cot_cua_bang(cur, bang):
    cur.execute(
        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
        "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? ORDER BY ORDINAL_POSITION",
        bang,
    )
    return [dict(ten=r[0], kieu=r[1], null=r[2] == "YES", mac_dinh=r[3]) for r in cur.fetchall()]


def kiem_ten_cot(cot_bang, can, ten_bang):
    co = {c["ten"].lower() for c in cot_bang}
    thieu = [c for c in can if c.lower() not in co]
    if thieu:
        raise SystemExit(f"Bảng {ten_bang} KHÔNG có cột {thieu}. Sửa config rồi chạy lại. Chưa ghi gì.")


def cot_bat_buoc_chua_co(cot_bang, se_ghi):
    """Cột NOT NULL, không default, không identity, mà ta không ghi -> INSERT sẽ lỗi."""
    se_ghi = {c.lower() for c in se_ghi}
    return [
        c["ten"]
        for c in cot_bang
        if not c["null"] and c["mac_dinh"] is None and c["ten"].lower() not in se_ghi
    ]


# ----------------------------------------------------------------- đọc lô
def tim_cot(tieu_de, tu_khoa, ten_cau_hinh=None):
    """Tìm vị trí cột theo tên cấu hình (chính xác) hoặc theo từ khóa (bỏ dấu, chứa)."""
    chuan = [bo_dau(t) for t in tieu_de]
    if ten_cau_hinh:
        muon = bo_dau(ten_cau_hinh)
        if muon in chuan:
            return chuan.index(muon)
    for i, t in enumerate(chuan):
        if all(k in t for k in tu_khoa):
            return i
    return None


def doc_xlsx(duong_dan, so_dong_max=None):
    from openpyxl import load_workbook

    wb = load_workbook(duong_dan, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    dong = list(ws.iter_rows(values_only=True))
    wb.close()
    tieu_de = [str(c).strip() if c is not None else "" for c in dong[0]]
    than = [r for r in dong[1:] if any(c not in (None, "") for c in r)]
    return tieu_de, than[:so_dong_max] if so_dong_max else than


def so_thuc(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(".", "").replace(",", ".").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def phan_tram(v):
    """Chuẩn về tỉ lệ 0..1: 12 -> 0.12 ; 0.12 -> 0.12."""
    x = so_thuc(v)
    if x is None:
        return None
    return x / 100.0 if abs(x) > 1.0 else x


def loc_lo(tieu_de, than, cfg_lo):
    """Trả (danh sách mã sạch, danh sách bị loại kèm lý do). Thuần Python, có test."""
    i_ma = tim_cot(tieu_de, ["ma"], cfg_lo.get("cot_ma"))
    i_gia = tim_cot(tieu_de, ["gia", "si"], cfg_lo.get("cot_gia_si"))
    i_lai = tim_cot(tieu_de, ["lai"], cfg_lo.get("cot_lai_tren_von"))
    if None in (i_ma, i_gia, i_lai):
        raise SystemExit(
            f"Không tìm được cột trong file lô. Tiêu đề: {tieu_de}. "
            f"Mã={i_ma} GiáSỉ={i_gia} Lãi={i_lai}. Điền cot_ma/cot_gia_si/cot_lai_tren_von trong config."
        )
    nguong = float(cfg_lo.get("lai_toi_da", 0.10))
    loai_tru = {str(m).strip().upper() for m in cfg_lo.get("loai_tru_ma", [])}
    sach, loai = [], []
    da_thay = set()
    for r in than:
        ma = str(r[i_ma] or "").strip().upper()
        gia = so_thuc(r[i_gia])
        lai = phan_tram(r[i_lai])
        if not ma:
            continue
        if ma in da_thay:
            loai.append((ma, gia, lai, "trùng mã trong file"))
            continue
        da_thay.add(ma)
        if gia is None or gia <= 0:
            loai.append((ma, gia, lai, "giá sỉ trống/không hợp lệ"))
        elif ma in loai_tru:
            loai.append((ma, gia, lai, "trong danh sách loại trừ"))
        elif lai is None:
            loai.append((ma, gia, lai, "thiếu lãi trên vốn"))
        elif lai <= 0:
            loai.append((ma, gia, lai, "lãi trên vốn <= 0 (dưới sàn vốn)"))
        elif lai > nguong:
            loai.append((ma, gia, lai, f"lãi trên vốn > {nguong:.0%} (nghi ghép nhầm)"))
        else:
            sach.append((ma, int(round(gia)), lai))
    return sach, loai


# ----------------------------------------------------------------- kiểm chốt tại DB
def kiem_chot_db(cur, cfg, sach):
    """Đối chiếu từng mã với MATHANG hiện tại: phải tồn tại, giá sỉ < giá lẻ hiện hành."""
    mh = cfg["mathang"]
    cur.execute("IF OBJECT_ID('tempdb..#lo') IS NOT NULL DROP TABLE #lo")
    cur.execute("CREATE TABLE #lo (MA NVARCHAR(100) PRIMARY KEY, GIASI DECIMAL(18,2))")
    cur.fast_executemany = True
    cur.executemany("INSERT INTO #lo (MA, GIASI) VALUES (?, ?)", [(m, g) for m, g, _ in sach])
    cur.execute(
        f"""
        SELECT l.MA, l.GIASI, m.{mh['cot_gia_le']} AS GIALE, m.GIABANBUON AS SI_HIEN_TAI,
               m.{mh['cot_ten']} AS TEN
        FROM #lo l LEFT JOIN dbo.MATHANG m ON m.{mh['cot_ma']} = l.MA
        """
    )
    ok, loi = [], []
    for ma, gia_si, gia_le, si_cu, ten in cur.fetchall():
        if ten is None:
            loi.append((ma, gia_si, "không có trong MATHANG"))
        elif gia_le is not None and float(gia_si) >= float(gia_le):
            loi.append((ma, gia_si, f"giá sỉ >= giá lẻ hiện tại ({gia_le})"))
        else:
            ok.append(dict(ma=ma, gia_si=float(gia_si), gia_le=gia_le, si_cu=si_cu, ten=ten))
    return ok, loi


# ----------------------------------------------------------------- ghi
def ghi_that(cur, cfg, ok, log):
    mh, gs = cfg["mathang"], cfg["dmv_gisi"]
    ngay = gio_vn().strftime("%Y%m%d")
    bak_mh = f"bak_MATHANG_GIABANBUON_{ngay}"
    bak_gs = f"bak_{gs['bang']}_{ngay}"
    n = len(ok)

    # 1. Backup (idempotent: bảng đã có thì giữ, không ghi đè ảnh trước)
    cur.execute(f"SELECT OBJECT_ID('dbo.{bak_mh}'), OBJECT_ID('dbo.{bak_gs}')")
    co_mh, co_gs = cur.fetchone()
    if co_mh is None:
        cur.execute(
            f"SELECT m.{mh['cot_ma']} AS MA, m.GIABANBUON, SYSDATETIME() AS LUC_BACKUP "
            f"INTO dbo.{bak_mh} FROM dbo.MATHANG m JOIN #lo l ON l.MA = m.{mh['cot_ma']}"
        )
        log(f"Backup MATHANG -> dbo.{bak_mh}: {cur.rowcount} dòng")
    else:
        log(f"Backup dbo.{bak_mh} đã có từ trước, giữ nguyên.")
    if co_gs is None:
        cur.execute(f"SELECT * INTO dbo.{bak_gs} FROM dbo.{gs['bang']}")
        log(f"Backup {gs['bang']} -> dbo.{bak_gs}: {cur.rowcount} dòng")
    else:
        log(f"Backup dbo.{bak_gs} đã có từ trước, giữ nguyên.")

    # 2. dmv_GiaSi: thêm mã chưa có, cập nhật mã đã có mà giá khác
    them = ", ".join(f"[{k}]" for k in gs.get("cot_them", {}))
    gia_tri_them = ", ".join("?" for _ in gs.get("cot_them", {}))
    tham_so_them = list(gs.get("cot_them", {}).values())
    cur.execute(
        f"""
        UPDATE g SET g.[{gs['cot_gia']}] = l.GIASI
        FROM dbo.{gs['bang']} g JOIN #lo l ON g.[{gs['cot_ma']}] = l.MA
        WHERE ISNULL(g.[{gs['cot_gia']}], -1) <> l.GIASI
        """
    )
    n_gs_upd = cur.rowcount
    cur.execute(
        f"""
        INSERT INTO dbo.{gs['bang']} ([{gs['cot_ma']}], [{gs['cot_gia']}]{', ' + them if them else ''})
        SELECT l.MA, l.GIASI{', ' + gia_tri_them if them else ''}
        FROM #lo l WHERE NOT EXISTS (SELECT 1 FROM dbo.{gs['bang']} g WHERE g.[{gs['cot_ma']}] = l.MA)
        """,
        tham_so_them,
    )
    n_gs_ins = cur.rowcount
    log(f"{gs['bang']}: thêm {n_gs_ins}, cập nhật {n_gs_upd}")

    # 3. MATHANG.GIABANBUON: chỉ sửa dòng còn lệch
    cur.execute(
        f"""
        UPDATE m SET m.GIABANBUON = l.GIASI
        FROM dbo.MATHANG m JOIN #lo l ON m.{mh['cot_ma']} = l.MA
        WHERE ISNULL(m.GIABANBUON, -1) <> l.GIASI
        """
    )
    n_mh = cur.rowcount
    log(f"MATHANG.GIABANBUON: cập nhật {n_mh} dòng (lô {n} mã)")

    # 4. Chốt: không được vượt quá số mã trong lô
    if n_gs_ins + n_gs_upd > n or n_mh > n:
        raise RuntimeError(f"Số dòng ghi vượt lô ({n}): dmv={n_gs_ins}+{n_gs_upd}, MATHANG={n_mh}")
    # Đối chiếu sau ghi
    cur.execute(
        f"SELECT COUNT(*) FROM dbo.MATHANG m JOIN #lo l ON m.{mh['cot_ma']} = l.MA "
        "WHERE ISNULL(m.GIABANBUON,-1) <> l.GIASI"
    )
    con_lech = cur.fetchone()[0]
    if con_lech:
        raise RuntimeError(f"Sau ghi vẫn còn {con_lech} mã lệch giá sỉ.")
    return dict(backup_mathang=bak_mh, backup_giasi=bak_gs, gs_ins=n_gs_ins, gs_upd=n_gs_upd, mh=n_mh)


# ----------------------------------------------------------------- xuất kết quả
def xuat_xlsx(thu_muc, ok, loi_db, loai_file, tom_tat):
    from openpyxl import Workbook

    os.makedirs(thu_muc, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Da ghi"
    ws.append(["Mã hàng", "Tên hàng", "Giá sỉ ghi", "Giá sỉ cũ", "Giá lẻ hiện tại"])
    for r in ok:
        ws.append([r["ma"], r["ten"], r["gia_si"], r["si_cu"], r["gia_le"]])
    ws2 = wb.create_sheet("Bi loai")
    ws2.append(["Mã hàng", "Giá sỉ", "Lãi trên vốn", "Lý do"])
    for ma, gia, lai, ly_do in loai_file:
        ws2.append([ma, gia, lai, ly_do])
    for ma, gia, ly_do in loi_db:
        ws2.append([ma, gia, None, "DB: " + ly_do])
    ws3 = wb.create_sheet("Tom tat")
    for k, v in tom_tat.items():
        ws3.append([k, str(v)])
    wb.properties.creator = NGUOI_TAO
    duong_dan = os.path.join(thu_muc, ten_file("Ket Qua Ghi Lo Gia Si Lan Dau", "xlsx"))
    wb.save(duong_dan)
    return duong_dan


# ----------------------------------------------------------------- main
def kham_pha(cfg, log):
    tieu_de, than = doc_xlsx(cfg["file_lo"], so_dong_max=3)
    log("== FILE LÔ:", cfg["file_lo"])
    log("Tiêu đề:", tieu_de)
    for r in than:
        log("  mẫu:", r)
    with ket_noi(cfg["sql"]) as cn:
        cur = cn.cursor()
        for bang in ("MATHANG", cfg["dmv_gisi"]["bang"], "dmv_Rule_Gia"):
            cot = cot_cua_bang(cur, bang)
            if bang == "MATHANG":
                cot = [c for c in cot if re.search(r"gia|mhid|mhcode|mhten|hasdetail", c["ten"], re.I)]
            log(f"== BẢNG {bang} ({len(cot)} cột liên quan):")
            for c in cot:
                log(f"  {c['ten']:<30} {c['kieu']:<12} {'NULL' if c['null'] else 'NOT NULL':<9} default={c['mac_dinh']}")
    log("Khám phá xong. Đối chiếu với config.json rồi chạy xem trước.")


def chay(cfg, ghi, log):
    tieu_de, than = doc_xlsx(cfg["file_lo"])
    sach, loai_file = loc_lo(tieu_de, than, cfg["lo"])
    log(f"File lô: {len(than)} dòng -> {len(sach)} mã sạch, {len(loai_file)} bị loại theo file.")
    mong_doi = int(cfg["lo"]["so_ma_mong_doi"])
    if len(sach) != mong_doi:
        for ma, gia, lai, ly_do in loai_file[:40]:
            log("  loại:", ma, gia, lai, ly_do)
        raise SystemExit(f"DỪNG: số mã sạch {len(sach)} ≠ mong đợi {mong_doi}. Chưa ghi gì.")

    with ket_noi(cfg["sql"]) as cn:
        cur = cn.cursor()
        mh, gs = cfg["mathang"], cfg["dmv_gisi"]
        cot_mh = cot_cua_bang(cur, "MATHANG")
        kiem_ten_cot(cot_mh, [mh["cot_ma"], mh["cot_ten"], mh["cot_gia_le"], "GIABANBUON"], "MATHANG")
        cot_gs = cot_cua_bang(cur, gs["bang"])
        if not cot_gs:
            raise SystemExit(f"Không thấy bảng {gs['bang']}.")
        kiem_ten_cot(cot_gs, [gs["cot_ma"], gs["cot_gia"], *gs.get("cot_them", {})], gs["bang"])
        thieu = cot_bat_buoc_chua_co(cot_gs, [gs["cot_ma"], gs["cot_gia"], *gs.get("cot_them", {})])
        thieu = [c for c in thieu if c.lower() != "id"]  # identity thường tên ID
        if thieu:
            raise SystemExit(f"{gs['bang']} có cột NOT NULL chưa được ghi: {thieu}. Thêm vào cot_them.")

        ok, loi_db = kiem_chot_db(cur, cfg, sach)
        log(f"Kiểm chốt tại DB: {len(ok)} qua, {len(loi_db)} không qua.")
        for ma, gia, ly_do in loi_db:
            log("  không qua:", ma, gia, ly_do)
        if loi_db:
            cn.rollback()
            raise SystemExit("DỪNG: có mã không qua chốt an toàn tại DB. Chưa ghi gì.")

        log("== XEM TRƯỚC (10 dòng đầu):  mã | tên | sỉ cũ -> sỉ mới | lẻ hiện tại")
        for r in ok[:10]:
            log(f"  {r['ma']} | {str(r['ten'])[:40]} | {r['si_cu']} -> {r['gia_si']:.0f} | {r['gia_le']}")
        log(f"Tổng {len(ok)} mã sẽ ghi vào {gs['bang']} và MATHANG.GIABANBUON.")

        tom_tat = dict(so_ma=len(ok), loai_theo_file=len(loai_file), nguoi_tao=NGUOI_TAO, luc=gio_vn().isoformat())
        if not ghi:
            cn.rollback()
            log("Chế độ XEM TRƯỚC: không ghi gì. Chạy lại với --ghi để ghi thật.")
        else:
            xac_nhan = input(f"Gõ đúng chữ GHI để ghi {len(ok)} mã vào HTsoft (khác = hủy): ").strip()
            if xac_nhan != "GHI":
                cn.rollback()
                log("Hủy theo yêu cầu người chạy. Chưa ghi gì.")
                return
            try:
                kq = ghi_that(cur, cfg, ok, log)
                cn.commit()
                tom_tat.update(kq)
                log("ĐÃ COMMIT.", kq)
            except Exception as e:
                cn.rollback()
                log("LỖI -> ROLLBACK, không đổi gì:", repr(e))
                raise
    duong_dan = xuat_xlsx(cfg["thu_muc_ket_qua"], ok, loi_db, loai_file, tom_tat)
    log("File kết quả:", duong_dan)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
    p.add_argument("--kham-pha", action="store_true", help="chỉ đọc cấu trúc, không kiểm/ghi")
    p.add_argument("--ghi", action="store_true", help="ghi thật (vẫn hỏi gõ GHI)")
    a = p.parse_args(argv)
    cfg = doc_config(a.config)
    log = Log(cfg.get("thu_muc_log", os.path.dirname(os.path.abspath(a.config))))
    log("Bắt đầu", "KHÁM PHÁ" if a.kham_pha else ("GHI THẬT" if a.ghi else "XEM TRƯỚC"), "| config:", a.config)
    try:
        if a.kham_pha:
            kham_pha(cfg, log)
        else:
            chay(cfg, a.ghi, log)
    except SystemExit as e:
        log(str(e))
        raise
    log("Kết thúc. Log:", log.duong_dan)


if __name__ == "__main__":
    main()
