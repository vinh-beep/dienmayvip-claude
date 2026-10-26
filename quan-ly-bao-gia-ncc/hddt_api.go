package main

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

func dangKyHDDT(mux *http.ServeMux, kho *Kho, thuMucDuLieu string) {
	thuMucHD := filepath.Join(thuMucDuLieu, "hddt")
	doc := func(r *http.Request, v any) error { return json.NewDecoder(r.Body).Decode(v) }
	loi := func(w http.ResponseWriter, err error) { http.Error(w, err.Error(), 400) }

	mux.HandleFunc("/api/hddt", func(w http.ResponseWriter, r *http.Request) {
		c := kho.LayCauHinh()
		if c.IMAPMatKhau != "" {
			c.IMAPMatKhau = "********"
		}
		traJSON(w, map[string]any{"hoaDon": kho.CacHoaDon(), "cauHinh": c, "thuMucHD": thuMucHD, "tepBridge": TimTepLinkTrenBridge(c.ThuMucBridge)})
	})
	mux.HandleFunc("/api/hddt/cau-hinh", func(w http.ResponseWriter, r *http.Request) {
		var c CauHinhHDDT
		if err := doc(r, &c); err != nil {
			loi(w, err)
			return
		}
		if c.IMAPMatKhau == "********" {
			c.IMAPMatKhau = kho.LayCauHinh().IMAPMatKhau
		}
		if err := kho.LuuCauHinh(c); err != nil {
			loi(w, err)
			return
		}
		traJSON(w, map[string]bool{"ok": true})
	})

	// Dán nội dung email Fast e-Invoice (hoặc nhiều email nối nhau)
	mux.HandleFunc("/api/hddt/nap-email", func(w http.ResponseWriter, r *http.Request) {
		var vao struct{ VanBan string }
		if err := doc(r, &vao); err != nil {
			loi(w, err)
			return
		}
		c := kho.LayCauHinh()
		var ds []*HoaDon
		for _, khoi := range tachKhoiEmail(vao.VanBan) {
			if hd := DocEmail(khoi); hd != nil && (hd.NCC == "" || khopNCC(hd, c.LocNCC, c.MSTNCC)) {
				ds = append(ds, hd)
			}
		}
		if len(ds) == 0 {
			loi(w, errors.New("không thấy hoá đơn (Fast e-Invoice / meinvoice) của NCC đang lọc trong nội dung dán"))
			return
		}
		n, err := kho.ThemHoaDon(ds)
		traKetQua(w, n, len(ds), err)
	})

	// Danh sách link do phiên Claude Cloud ghi lên Bridge (hddt-links-*.json) hoặc JSON dán tay
	mux.HandleFunc("/api/hddt/nap-bridge", func(w http.ResponseWriter, r *http.Request) {
		var vao struct{ JSON, Tep string }
		_ = doc(r, &vao)
		c := kho.LayCauHinh()
		var ds []*HoaDon
		var nguon []string
		if vao.JSON != "" {
			x, err := DocDanhSachLink([]byte(vao.JSON))
			if err != nil {
				loi(w, fmt.Errorf("JSON lỗi: %v", err))
				return
			}
			ds = append(ds, x...)
			nguon = append(nguon, "dán tay")
		} else {
			teps := TimTepLinkTrenBridge(c.ThuMucBridge)
			if vao.Tep != "" {
				teps = []string{vao.Tep}
			}
			for _, t := range teps {
				b, err := os.ReadFile(t)
				if err != nil {
					continue
				}
				if x, err := DocDanhSachLink(b); err == nil {
					ds = append(ds, x...)
					nguon = append(nguon, filepath.Base(t))
				}
			}
		}
		var loc []*HoaDon
		for _, hd := range ds {
			if hd.NCC == "" || khopNCC(hd, c.LocNCC, c.MSTNCC) {
				loc = append(loc, hd)
			}
		}
		if len(loc) == 0 {
			loi(w, fmt.Errorf("không có hoá đơn nào trong %d tệp hddt-links-*.json tại %s", len(nguon), c.ThuMucBridge))
			return
		}
		n, err := kho.ThemHoaDon(loc)
		traKetQua(w, n, len(loc), err)
	})

	mux.HandleFunc("/api/hddt/imap", func(w http.ResponseWriter, r *http.Request) {
		c := kho.LayCauHinh()
		if c.IMAPUser == "" || c.IMAPMatKhau == "" {
			loi(w, errors.New("chưa có tài khoản/mật khẩu ứng dụng IMAP trong Cấu hình"))
			return
		}
		thu, err := TimEmailHDDTIMAP(c.IMAPUser, c.IMAPMatKhau, c.NguoiGuiHDDT, c.IMAPTuNgay, 500)
		if err != nil {
			loi(w, err)
			return
		}
		var ds []*HoaDon
		dinhKem := 0
		for _, t := range thu {
			hd := DocEmail(t.Text)
			var xmlDu, pdfDu, xmlTho []byte // xmlTho: đính kèm không đọc được, vẫn lưu để xử lý tay
			for _, d := range t.DinhKem {
				if strings.HasSuffix(strings.ToLower(d.Ten), ".pdf") {
					if pdfDu == nil {
						pdfDu = d.Du
					}
					continue
				}
				if xmlDu != nil {
					continue
				}
				tamHD := HoaDon{TrangThai: "moi"}
				if hd != nil {
					tamHD = *hd // giữ link/mã tra cứu từ thân thư, XML ghi đè phần còn lại
				}
				if DocXMLHoaDon(d.Du, &tamHD) == nil {
					hd, xmlDu = &tamHD, d.Du
				} else if xmlTho == nil {
					xmlTho = d.Du
				}
			}
			if hd == nil || !khopNCC(hd, c.LocNCC, c.MSTNCC) {
				continue
			}
			hd.Nguon = "imap"
			tm := filepath.Join(thuMucHD, tenThuMuc(hd.NCC))
			ghi := func(du []byte, duoi string) string {
				if du == nil {
					return ""
				}
				_ = os.MkdirAll(tm, 0o755)
				p := filepath.Join(tm, tenTepHD(hd, duoi))
				if err := os.WriteFile(p, du, 0o644); err != nil {
					return ""
				}
				dinhKem++
				return p
			}
			duoiXML := ".xml"
			if bytes.HasPrefix(xmlDu, []byte("PK")) {
				duoiXML = ".zip"
			}
			if p := ghi(xmlDu, duoiXML); p != "" {
				hd.TepXML = p
			}
			if xmlDu == nil && xmlTho != nil { // lưu bản thô để xử lý tay, KHÔNG gán TepXML để còn tải lại được
				if p := ghi(xmlTho, ".dinh-kem-khong-doc-duoc.xml"); p != "" {
					hd.Loi = "đính kèm XML không đọc được, đã lưu: " + filepath.Base(p)
				}
			}
			if p := ghi(pdfDu, ".pdf"); p != "" {
				hd.TepPDF = p
			}
			ds = append(ds, hd)
		}
		n, err := kho.ThemHoaDon(ds)
		if err == nil && len(ds) == 0 {
			traJSON(w, map[string]any{"moi": 0, "tong": 0, "thongBao": fmt.Sprintf("Đọc %d thư HĐĐT, không có thư nào của NCC đang lọc (%s)", len(thu), c.LocNCC)})
			return
		}
		if err == nil {
			traJSON(w, map[string]any{"moi": n, "tong": len(ds), "thongBao": fmt.Sprintf("Đọc %d thư, %d hoá đơn của NCC đang lọc, %d mới, %d tệp đính kèm đã lưu", len(thu), len(ds), n, dinhKem)})
			return
		}
		traKetQua(w, n, len(ds), err)
	})

	// Everything / es.exe / quét thư mục → đọc XML, gắn PDF theo số HĐ
	timTep := func(w http.ResponseWriter, r *http.Request, cach string) {
		c := kho.LayCauHinh()
		var vao struct{ TruyVan string }
		_ = doc(r, &vao)
		tv := vao.TruyVan
		if tv == "" {
			var tu []string
			for _, n := range tachDS(c.LocNCC) {
				n = strings.ToLower(boDau(n))
				tu = append(tu, strings.ReplaceAll(n, " ", ""), `"`+n+`"`)
			}
			tu = append(tu, "hoadon", `"hoa don"`, "hddt", "invoice", "*C2?T*", "*C2?M*", "1C2*", "C2*")
			tv = `ext:xml;zip;pdf ` + strings.Join(tu, "|")
		}
		var tep []ketQuaTep
		var err error
		switch cach {
		case "everything":
			tep, err = TimEverything(c.EverythingURL, tv, 2000)
			if err != nil {
				if t2, err2 := TimES(tv, 2000); err2 == nil {
					tep, err = t2, nil
				}
			}
		default:
			tep = QuetThuMuc(c.ThuMucQuet)
		}
		if err != nil {
			loi(w, err)
			return
		}
		var ds []*HoaDon
		var pdf []string
		daDoc, boQua := 0, 0
		for _, t := range tep {
			switch strings.ToLower(filepath.Ext(t.Duong)) {
			case ".xml", ".zip":
				if t.KichCo > 30<<20 {
					continue
				}
				hd, err := DocTepHoaDon(t.Duong, c.LocNCC, c.MSTNCC)
				if err != nil {
					boQua++
					continue
				}
				hd.Nguon = cach
				ds = append(ds, hd)
				daDoc++
			case ".pdf":
				pdf = append(pdf, t.Duong)
			}
		}
		// Gắn PDF: tên tệp chứa số HĐ (và ký hiệu nếu có)
		for _, hd := range append(ds, kho.CacHoaDon()...) {
			if hd.TepPDF != "" || hd.So == "" {
				continue
			}
			khop := taoKhopPDF(hd.So, hd.KyHieu)
			for _, p := range pdf {
				if khop(filepath.Base(p)) {
					hd.TepPDF = p
					break
				}
			}
		}
		n, err := kho.ThemHoaDon(ds)
		if err != nil {
			loi(w, err)
			return
		}
		_ = kho.LuuHoaDon()
		traJSON(w, map[string]any{"moi": n, "tong": len(ds), "thongBao": fmt.Sprintf("%s: %d tệp tìm thấy, %d XML đúng NCC, %d XML khác/lỗi, %d PDF, %d hoá đơn mới", cach, len(tep), daDoc, boQua, len(pdf), n)})
	}
	mux.HandleFunc("/api/hddt/everything", func(w http.ResponseWriter, r *http.Request) { timTep(w, r, "everything") })
	mux.HandleFunc("/api/hddt/quet", func(w http.ResponseWriter, r *http.Request) { timTep(w, r, "thu-muc") })

	// Tải XML/PDF từ link Fast cho 1 hoặc tất cả hoá đơn chưa có tệp
	mux.HandleFunc("/api/hddt/tai", func(w http.ResponseWriter, r *http.Request) {
		var vao struct{ ID int64 }
		_ = doc(r, &vao)
		var ds []*HoaDon
		for _, hd := range kho.CacHoaDon() {
			if (vao.ID == 0 || hd.ID == vao.ID) && (hd.LinkXML != "" || hd.LinkPDF != "") && (vao.ID != 0 || hd.TepXML == "" || hd.TepPDF == "") {
				ds = append(ds, hd)
			}
		}
		ok, hong := 0, 0
		var loiDs []string
		for _, hd := range ds {
			if err := TaiHoaDon(hd, filepath.Join(thuMucHD, tenThuMuc(hd.NCC))); err != nil {
				hong++
				loiDs = append(loiDs, hd.KyHieu+"-"+hd.So+": "+err.Error())
			} else {
				ok++
			}
		}
		_ = kho.LuuHoaDon()
		traJSON(w, map[string]any{"ok": ok, "loi": hong, "chiTiet": loiDs, "thongBao": fmt.Sprintf("Tải xong %d, lỗi %d (trong %d hoá đơn có link)", ok, hong, len(ds))})
	})

	mux.HandleFunc("/api/hddt/doc-tep", func(w http.ResponseWriter, r *http.Request) {
		var vao struct{ ID int64 }
		_ = doc(r, &vao)
		hd := kho.HoaDonTheoID(vao.ID)
		if hd == nil || hd.TepXML == "" {
			loi(w, errors.New("hoá đơn chưa có tệp XML"))
			return
		}
		b, err := os.ReadFile(hd.TepXML)
		if err == nil {
			err = DocXMLHoaDon(b, hd)
		}
		if err != nil {
			hd.Loi = err.Error()
		}
		_ = kho.LuuHoaDon()
		if err != nil {
			loi(w, err)
			return
		}
		traJSON(w, hd)
	})

	mux.HandleFunc("/api/hddt/chi-tiet", func(w http.ResponseWriter, r *http.Request) {
		id, _ := strconv.ParseInt(r.URL.Query().Get("id"), 10, 64)
		hd := kho.HoaDonTheoID(id)
		if hd == nil {
			loi(w, errors.New("không thấy"))
			return
		}
		bg := kho.TatCa()
		type dc struct {
			DongHD
			BaoGia *DongGia `json:"baoGia"`
		}
		var ds []dc
		for _, d := range hd.Dong {
			ds = append(ds, dc{d, DoiChieu(d, hd.NgayLap, bg)})
		}
		traJSON(w, map[string]any{"hoaDon": hd, "dong": ds})
	})

	mux.HandleFunc("/api/hddt/mo", func(w http.ResponseWriter, r *http.Request) {
		id, _ := strconv.ParseInt(r.URL.Query().Get("id"), 10, 64)
		hd := kho.HoaDonTheoID(id)
		if hd == nil {
			loi(w, errors.New("không thấy"))
			return
		}
		tep := hd.TepXML
		if tep == "" {
			tep = hd.TepPDF
		}
		thuMuc := ""
		if tep != "" {
			thuMuc = filepath.Dir(tep)
		}
		duong := map[string]string{"pdf": hd.TepPDF, "xml": hd.TepXML, "thu-muc": thuMuc}[r.URL.Query().Get("loai")]
		if duong == "" || duong == "." {
			loi(w, errors.New("chưa có tệp"))
			return
		}
		moTep(duong)
		traJSON(w, map[string]bool{"ok": true})
	})

	mux.HandleFunc("/api/hddt/xoa", func(w http.ResponseWriter, r *http.Request) {
		var vao struct{ ID int64 }
		_ = doc(r, &vao)
		if err := kho.XoaHoaDon(vao.ID); err != nil {
			loi(w, err)
			return
		}
		traJSON(w, map[string]bool{"ok": true})
	})

	mux.HandleFunc("/api/hddt/xuat-csv", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/csv; charset=utf-8")
		w.Header().Set("Content-Disposition", `attachment; filename="HDDT NCC `+time.Now().Format("02 01 2006 15h04p")+`.csv"`)
		w.Write([]byte("\xEF\xBB\xBF"))
		cw := csv.NewWriter(w)
		cw.Write([]string{"SoHD", "KyHieu", "MauSo", "NgayLap", "NCC", "MST", "TenHang", "DVT", "SL", "DonGia", "ThanhTien", "TongTT_HD", "Nguon", "TepXML", "TepPDF"})
		for _, hd := range kho.CacHoaDon() {
			if len(hd.Dong) == 0 {
				cw.Write([]string{hd.So, hd.KyHieu, hd.MauSo, hd.NgayLap, hd.NCC, hd.MST, "", "", "", "", "", strconv.FormatInt(hd.TongTT, 10), hd.Nguon, hd.TepXML, hd.TepPDF})
			}
			for _, d := range hd.Dong {
				cw.Write([]string{hd.So, hd.KyHieu, hd.MauSo, hd.NgayLap, hd.NCC, hd.MST, d.Ten, d.DVT, strconv.FormatFloat(d.SL, 'f', -1, 64), strconv.FormatInt(d.DonGia, 10), strconv.FormatInt(d.ThanhTien, 10), strconv.FormatInt(hd.TongTT, 10), hd.Nguon, hd.TepXML, hd.TepPDF})
			}
		}
		cw.Flush()
	})
}

var reKyHieuTrongTen = regexp.MustCompile(`\d?[CK]2\d[A-Z]{3}`)

// taoKhopPDF trả về hàm kiểm tên tệp PDF cho một hoá đơn (biên dịch regex một lần cho mỗi hoá đơn):
// tên tệp (sau khi bỏ cụm ký hiệu) phải chứa số HĐ như một cụm số riêng (cho phép số 0 đệm);
// nếu tên có ký hiệu và hoá đơn cũng có ký hiệu thì hai bên phải trùng.
func taoKhopPDF(so, kyHieu string) func(tenTep string) bool {
	if so == "" {
		return func(string) bool { return false }
	}
	reSo := regexp.MustCompile(`(^|[^0-9])0*` + regexp.QuoteMeta(so) + `([^0-9]|$)`)
	return func(tenTep string) bool {
		ten := strings.ToUpper(tenTep)
		kh := reKyHieuTrongTen.FindString(ten)
		if kh != "" {
			ten = strings.Replace(ten, kh, " ", 1) // không cho số HĐ khớp vào chữ số của ký hiệu (C26…)
		}
		if !reSo.MatchString(ten) {
			return false
		}
		if kh != "" && kyHieu != "" {
			return chuanKyHieu(kh) == chuanKyHieu(kyHieu)
		}
		return true
	}
}

func khopTenPDF(tenTep, so, kyHieu string) bool { return taoKhopPDF(so, kyHieu)(tenTep) }

// tachKhoiEmail tách văn bản dán nhiều email thành từng thư (cắt tại tiêu đề mỗi thư).
func tachKhoiEmail(s string) []string {
	re := regexp.MustCompile(`(?m)^.*(Fast e-Invoice|thông báo gửi Hóa đơn)`)
	viTri := re.FindAllStringIndex(s, -1)
	var ket []string
	bat := 0
	for i, v := range viTri {
		if i == 0 || v[0]-bat < 150 {
			continue
		}
		ket = append(ket, s[bat:v[0]])
		bat = v[0]
	}
	return append(ket, s[bat:])
}

func traKetQua(w http.ResponseWriter, moi, tong int, err error) {
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	traJSON(w, map[string]any{"moi": moi, "tong": tong, "thongBao": fmt.Sprintf("Đọc được %d hoá đơn, %d mới (còn lại đã có, chỉ bổ sung link)", tong, moi)})
}

func tenThuMuc(s string) string {
	s = strings.ToUpper(boDau(s))
	if s == "" {
		return "khac"
	}
	for _, t := range []string{"CONG TY TNHH THUONG MAI - DICH VU ", "CONG TY TNHH ", "CONG TY CO PHAN ", "CONG TY "} {
		s = strings.TrimPrefix(s, t)
	}
	s = strings.Map(func(r rune) rune {
		if r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' {
			return r
		}
		return '-'
	}, s)
	return strings.Trim(s, "-")
}

func moTep(duong string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", duong)
	case "darwin":
		cmd = exec.Command("open", duong)
	default:
		cmd = exec.Command("xdg-open", duong)
	}
	_ = cmd.Start()
}
