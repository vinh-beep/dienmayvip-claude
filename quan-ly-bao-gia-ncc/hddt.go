package main

// HĐĐT: tìm và nạp hoá đơn điện tử của NCC vào app.
// Nguồn: (1) email Fast e-Invoice (link tải XML/PDF), (2) Everything HTTP server,
// (3) quét thư mục, (4) danh sách link do phiên Claude Cloud ghi lên Bridge, (5) IMAP Gmail.

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

type DongHD struct {
	Ten       string  `json:"ten"`
	DVT       string  `json:"dvt"`
	SL        float64 `json:"sl"`
	DonGia    int64   `json:"donGia"`
	ThanhTien int64   `json:"thanhTien"`
}

type HoaDon struct {
	ID         int64    `json:"id"`
	So         string   `json:"so"`
	KyHieu     string   `json:"kyHieu"`
	MauSo      string   `json:"mauSo"`
	NgayLap    string   `json:"ngayLap"` // dd/mm/yyyy
	NCC        string   `json:"ncc"`
	MST        string   `json:"mst"`
	MaCQT      string   `json:"maCQT"` // mã cơ quan thuế
	TienHang   int64    `json:"tienHang"`
	Thue       int64    `json:"thue"`
	TongTT     int64    `json:"tongTT"`
	Nguon      string   `json:"nguon"` // email | bridge | everything | thu-muc | imap | tay
	EmailNgay  string   `json:"emailNgay"`
	LinkTraCuu string   `json:"linkTraCuu"`
	MaTraCuu   string   `json:"maTraCuu"`
	LinkXML    string   `json:"linkXML"`
	LinkPDF    string   `json:"linkPDF"`
	TepXML     string   `json:"tepXML"`
	TepPDF     string   `json:"tepPDF"`
	TrangThai  string   `json:"trangThai"` // moi | da-tai | da-doc | loi
	Loi        string   `json:"loi"`
	Dong       []DongHD `json:"dong"`
	TaoLuc     string   `json:"taoLuc"`
}

type CauHinhHDDT struct {
	EverythingURL string   `json:"everythingURL"` // vd http://127.0.0.1:8080
	ThuMucQuet    []string `json:"thuMucQuet"`
	ThuMucBridge  string   `json:"thuMucBridge"` // G:\My Drive\DMV-Cloud-Bridge
	LocNCC        string   `json:"locNCC"`       // danh sách tên NCC lọc, cách nhau dấu phẩy
	MSTNCC        string   `json:"mstNCC"`       // danh sách MST, cách nhau dấu phẩy
	NguoiGuiHDDT  string   `json:"nguoiGuiHDDT"` // địa chỉ gửi HĐĐT cho IMAP, cách nhau dấu phẩy
	IMAPUser      string   `json:"imapUser"`
	IMAPMatKhau   string   `json:"imapMatKhau"` // mật khẩu ứng dụng Google
	IMAPTuNgay    string   `json:"imapTuNgay"`  // dd/mm/yyyy
}

func cauHinhMacDinh() CauHinhHDDT {
	return CauHinhHDDT{
		EverythingURL: "http://127.0.0.1:8080",
		ThuMucQuet:    []string{`D:\VIP DATA\03 Ke Toan HDDT`, filepath.Join(os.Getenv("USERPROFILE"), "Downloads")},
		ThuMucBridge:  `G:\My Drive\DMV-Cloud-Bridge`,
		LocNCC:        "KHUONG VIET, TCT, LONG HUNG, THANH LIEM",
		NguoiGuiHDDT:  "einvoice@fastsoftware.com.vn, no-reply@meinvoice.vn, hddt@longhungmobile.com, ctythanhliem1.ct@gmail.com",
		IMAPUser:      "vinh@dienmayvip.com",
		IMAPTuNgay:    "01/01/2024",
	}
}

// ---------- Email Fast e-Invoice ----------

var (
	reSoHD     = regexp.MustCompile(`(?i)Số hóa đơn[^:]*:\s*\*?\s*([0-9]+)`)
	reKyHieu   = regexp.MustCompile(`(?i)Ký hiệu hóa đơn[^:]*:\s*\*?\s*([A-Z0-9]+)`)
	reMauSo    = regexp.MustCompile(`(?i)Mẫu số hóa đơn[^:]*:\s*\*?\s*([0-9]+)`)
	reLink     = regexp.MustCompile(`https://einvoice\.fast\.com\.vn/index\.aspx\?[^\s)"'<>\]]+`)
	reMaTC     = regexp.MustCompile(`(?i)Secure Key for searching\)\*?:\s*\*?\s*([A-Za-z0-9+/=]+)`)
	reNguoiBan = regexp.MustCompile(`(?m)^\s*\*?\s*(CÔNG TY[^\n*]+?)\s*\*?\s*xin gửi cho Quý khách`)
)

var (
	reMisaSo    = regexp.MustCompile(`(?im)(?:^|[^ã\s])\s*Số:\s*\*?\s*([0-9]+)`)
	reMisaNgay  = regexp.MustCompile(`(?i)Ngày:\s*\*?\s*(\d{2}/\d{2}/\d{4})`)
	reMisaKH    = regexp.MustCompile(`(?i)Ký hiệu:\s*\*?\s*([A-Z0-9]+)`)
	reMisaMaCQT = regexp.MustCompile(`(?i)Mã (?:của )?cơ quan thuế:\s*\*?\s*([A-Z0-9-]+)`)
	reMisaSC    = regexp.MustCompile(`(?i)meinvoice\.vn/tra-cuu/\?sc=([A-Z0-9_]+)`)
	reMisaMaTC  = regexp.MustCompile(`(?i)nhập mã số:\s*\*?\s*([A-Z0-9_]{8,})`)
	reMisaNBan  = regexp.MustCompile(`(?m)^\s*\*?\s*(CÔNG TY[^\n*]+?)\s+thông báo gửi Hóa đơn`)
)

// DocEmailMISA đọc email meinvoice.vn (TCT, Long Hưng, Thanh Liêm…). Link tải dựng từ mã tra cứu.
func DocEmailMISA(noiDung string) *HoaDon {
	if !strings.Contains(noiDung, "meinvoice.vn") {
		return nil
	}
	m := reMisaSo.FindStringSubmatch(noiDung)
	if m == nil {
		return nil
	}
	hd := &HoaDon{So: strings.TrimLeft(m[1], "0"), Nguon: "email", TrangThai: "moi"}
	if hd.So == "" {
		hd.So = m[1]
	}
	if k := reMisaNgay.FindStringSubmatch(noiDung); k != nil {
		hd.NgayLap = k[1]
	}
	if k := reMisaKH.FindStringSubmatch(noiDung); k != nil {
		hd.MauSo, hd.KyHieu = tachKyHieu(strings.ToUpper(k[1]))
	}
	if k := reMisaMaCQT.FindStringSubmatch(noiDung); k != nil {
		hd.MaCQT = k[1]
	}
	if k := reMisaNBan.FindStringSubmatch(noiDung); k != nil {
		hd.NCC = strings.TrimSpace(k[1])
	} else if k := reNguoiBan.FindStringSubmatch(noiDung); k != nil {
		hd.NCC = strings.TrimSpace(k[1])
	}
	sc := ""
	if k := reMisaSC.FindStringSubmatch(noiDung); k != nil {
		sc = strings.ToUpper(k[1])
	} else if k := reMisaMaTC.FindStringSubmatch(noiDung); k != nil {
		sc = strings.ToUpper(k[1])
	}
	if sc != "" {
		hd.MaTraCuu = sc
		hd.LinkTraCuu = "https://www.meinvoice.vn/tra-cuu/?sc=" + sc
		hd.LinkXML = "https://www.meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=" + sc
		hd.LinkPDF = "https://www.meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=pdf&Code=" + sc
	}
	return hd
}

// tachKyHieu: ký hiệu TT78 ghi liền mẫu số ("1C26TLH") → ("1", "C26TLH"); đã tách rồi thì giữ nguyên.
func tachKyHieu(kh string) (mauSo, kyHieu string) {
	if len(kh) >= 2 && kh[0] >= '0' && kh[0] <= '9' && (kh[1] == 'C' || kh[1] == 'K') {
		return kh[:1], kh[1:]
	}
	return "", kh
}

// chuanKyHieu dùng để so khớp: bỏ mẫu số đứng đầu, viết hoa.
func chuanKyHieu(kh string) string {
	_, k := tachKyHieu(strings.ToUpper(strings.TrimSpace(kh)))
	return k
}

// DocEmail nhận diện định dạng (Fast e-Invoice hoặc MISA meinvoice).
func DocEmail(noiDung string) *HoaDon {
	if hd := DocEmailFast(noiDung); hd != nil {
		return hd
	}
	return DocEmailMISA(noiDung)
}

// DocEmailFast đọc nội dung (text) email Fast e-Invoice. Trả về nil nếu không phải.
func DocEmailFast(noiDung string) *HoaDon {
	m := reSoHD.FindStringSubmatch(noiDung)
	if m == nil || !strings.Contains(noiDung, "einvoice.fast.com.vn") {
		return nil
	}
	hd := &HoaDon{So: strings.TrimLeft(m[1], "0"), Nguon: "email", TrangThai: "moi"}
	if hd.So == "" {
		hd.So = m[1]
	}
	if k := reKyHieu.FindStringSubmatch(noiDung); k != nil {
		hd.KyHieu = strings.ToUpper(k[1])
	}
	if k := reMauSo.FindStringSubmatch(noiDung); k != nil {
		hd.MauSo = k[1]
	}
	if k := reMaTC.FindStringSubmatch(noiDung); k != nil {
		hd.MaTraCuu = k[1]
	}
	if k := reNguoiBan.FindStringSubmatch(noiDung); k != nil {
		hd.NCC = strings.TrimSpace(k[1])
	}
	for _, l := range reLink.FindAllString(noiDung, -1) {
		l = strings.ReplaceAll(l, "&amp;", "&")
		u, err := url.Parse(l)
		if err != nil {
			continue
		}
		switch u.Query().Get("type") {
		case "2":
			hd.LinkXML = l
		case "3":
			hd.LinkPDF = l
		case "":
			if hd.LinkTraCuu == "" {
				hd.LinkTraCuu = l
			}
		}
	}
	return hd
}

// ---------- XML hoá đơn (chuẩn TT78 hoặc tương tự) ----------

type nutXML struct {
	Ten  string
	Text string
	Con  []*nutXML
}

func docCayXML(b []byte) (*nutXML, error) {
	d := xml.NewDecoder(bytes.NewReader(b))
	d.CharsetReader = func(_ string, r io.Reader) (io.Reader, error) { return r, nil }
	goc := &nutXML{Ten: "#root"}
	stack := []*nutXML{goc}
	for {
		t, err := d.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		switch x := t.(type) {
		case xml.StartElement:
			n := &nutXML{Ten: x.Name.Local}
			cha := stack[len(stack)-1]
			cha.Con = append(cha.Con, n)
			stack = append(stack, n)
		case xml.CharData:
			stack[len(stack)-1].Text += string(x)
		case xml.EndElement:
			if len(stack) > 1 {
				stack = stack[:len(stack)-1]
			}
		}
	}
	return goc, nil
}

func (n *nutXML) tim(ten ...string) *nutXML {
	for _, c := range n.Con {
		for _, t := range ten {
			if strings.EqualFold(c.Ten, t) {
				return c
			}
		}
	}
	for _, c := range n.Con {
		if r := c.tim(ten...); r != nil {
			return r
		}
	}
	return nil
}

func (n *nutXML) timTatCa(ten string, ra *[]*nutXML) {
	for _, c := range n.Con {
		if strings.EqualFold(c.Ten, ten) {
			*ra = append(*ra, c)
		} else {
			c.timTatCa(ten, ra)
		}
	}
}

func (n *nutXML) chu(ten ...string) string {
	if x := n.tim(ten...); x != nil {
		return strings.TrimSpace(x.Text)
	}
	return ""
}

func soTien(s string) int64 {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0
	}
	if i := strings.IndexAny(s, ".,"); i >= 0 && len(s)-i-1 <= 2 && !strings.ContainsAny(s[i+1:], ".,") {
		s = s[:i] // bỏ phần thập phân .00
	}
	s = strings.NewReplacer(".", "", ",", "", " ", "").Replace(s)
	n, _ := strconv.ParseInt(s, 10, 64)
	return n
}

func ngayVN(s string) string {
	s = strings.TrimSpace(s)
	for _, f := range []string{"2006-01-02", "2006-01-02T15:04:05", "02/01/2006", "2006-01-02 15:04:05"} {
		if t, err := time.Parse(f, s); err == nil {
			return t.Format("02/01/2006")
		}
	}
	if len(s) >= 10 {
		if t, err := time.Parse("2006-01-02", s[:10]); err == nil {
			return t.Format("02/01/2006")
		}
	}
	return s
}

// DocXMLHoaDon đọc XML (hoặc ZIP chứa XML) hoá đơn, điền vào hd (giữ link/nguồn cũ).
func DocXMLHoaDon(b []byte, hd *HoaDon) error {
	if bytes.HasPrefix(b, []byte("PK")) {
		zr, err := zip.NewReader(bytes.NewReader(b), int64(len(b)))
		if err != nil {
			return err
		}
		var xmlB []byte
		for _, f := range zr.File {
			if strings.HasSuffix(strings.ToLower(f.Name), ".xml") {
				rc, err := f.Open()
				if err != nil {
					return err
				}
				xmlB, _ = io.ReadAll(rc)
				rc.Close()
				break
			}
		}
		if xmlB == nil {
			return errors.New("ZIP không có tệp .xml")
		}
		b = xmlB
	}
	goc, err := docCayXML(b)
	if err != nil {
		return fmt.Errorf("XML lỗi: %v", err)
	}
	so := goc.chu("SHDon", "SoHD", "InvoiceNo", "InvoiceNumber", "SoHoaDon")
	if so == "" {
		return errors.New("không thấy số hoá đơn trong XML")
	}
	hd.So = strings.TrimLeft(so, "0")
	if hd.So == "" {
		hd.So = so
	}
	if k := goc.chu("KHHDon", "KyHieu", "SerialNo", "KyHieuHD"); k != "" {
		ms, kh := tachKyHieu(strings.ToUpper(k))
		hd.KyHieu = kh
		if ms != "" && hd.MauSo == "" {
			hd.MauSo = ms
		}
	}
	if k := goc.chu("KHMSHDon", "MauSo", "TemplateCode"); k != "" {
		hd.MauSo = k
	}
	if k := goc.chu("NLap", "NgayHD", "NgayLap", "InvoiceDate", "ArisingDate"); k != "" {
		hd.NgayLap = ngayVN(k)
	}
	if k := goc.chu("MCCQT", "MaCQT", "TaxAuthorityCode"); k != "" {
		hd.MaCQT = k
	}
	if nb := goc.tim("NBan", "SellerInfo", "NguoiBan", "Seller"); nb != nil {
		hd.NCC = nb.chu("Ten", "TenDonVi", "SellerLegalName", "Name")
		hd.MST = nb.chu("MST", "MaSoThue", "SellerTaxCode", "TaxCode")
	}
	if tt := goc.tim("TToan", "Total", "TongTien", "Payment"); tt != nil {
		hd.TienHang = soTien(tt.chu("TgTCThue", "TongTienChuaThue", "TotalAmountWithoutVAT", "Amount"))
		hd.Thue = soTien(tt.chu("TgTThue", "TongTienThue", "TotalVATAmount", "VATAmount"))
		hd.TongTT = soTien(tt.chu("TgTTTBSo", "TongTienThanhToan", "TotalAmount", "TotalAmountWithVAT"))
	}
	var hang []*nutXML
	goc.timTatCa("HHDVu", &hang)
	if len(hang) == 0 {
		goc.timTatCa("Product", &hang)
	}
	if len(hang) == 0 {
		goc.timTatCa("HangHoa", &hang)
	}
	hd.Dong = nil
	for _, h := range hang {
		d := DongHD{
			Ten: h.chu("THHDVu", "TenHang", "ProdName", "ProductName", "Name"),
			DVT: h.chu("DVTinh", "DonViTinh", "ProdUnit", "Unit"),
			SL:  0, DonGia: soTien(h.chu("DGia", "DonGia", "ProdPrice", "Price", "UnitPrice")),
			ThanhTien: soTien(h.chu("ThTien", "ThanhTien", "Amount", "ProdAmount")),
		}
		d.SL, _ = strconv.ParseFloat(strings.ReplaceAll(h.chu("SLuong", "SoLuong", "ProdQuantity", "Quantity"), ",", ""), 64)
		if d.Ten != "" {
			hd.Dong = append(hd.Dong, d)
		}
	}
	hd.TrangThai = "da-doc"
	hd.Loi = ""
	return nil
}

// ---------- Tải từ Fast ----------

var httpTai = &http.Client{Timeout: 90 * time.Second}

func taiTep(link string) ([]byte, string, error) {
	req, err := http.NewRequest("GET", link, nil)
	if err != nil {
		return nil, "", err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 QuanLyBaoGiaNCC")
	resp, err := httpTai.Do(req)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, "", fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	b, err := io.ReadAll(io.LimitReader(resp.Body, 30<<20))
	return b, resp.Header.Get("Content-Type"), err
}

func tenTepHD(hd *HoaDon, duoi string) string {
	ten := strings.Trim(strings.ReplaceAll(hd.KyHieu+"-"+hd.So, "/", "_"), "-")
	if ten == "" {
		ten = "hoa-don-" + strconv.FormatInt(hd.ID, 10)
	}
	return ten + duoi
}

// TaiHoaDon tải XML + PDF về thuMuc, đọc XML. Trả về lỗi đầu tiên (vẫn lưu phần tải được).
func TaiHoaDon(hd *HoaDon, thuMuc string) error {
	_ = os.MkdirAll(thuMuc, 0o755)
	var loi []string
	if hd.LinkXML != "" {
		b, ct, err := taiTep(hd.LinkXML)
		if err != nil {
			loi = append(loi, "XML: "+err.Error())
		} else if (strings.Contains(strings.ToLower(ct), "text/html") || bytes.Contains(bytes.ToLower(b[:min(len(b), 600)]), []byte("<html"))) && !bytes.Contains(b, []byte("<HDon")) && !bytes.Contains(b[:min(len(b), 600)], []byte("<?xml")) {
			loi = append(loi, "XML: máy chủ trả về trang web (mở link Tra cứu, nhập mã rồi tải thủ công vào thư mục quét)")
		} else {
			duoi := ".xml"
			if bytes.HasPrefix(b, []byte("PK")) {
				duoi = ".zip"
			}
			p := filepath.Join(thuMuc, tenTepHD(hd, duoi))
			if err := os.WriteFile(p, b, 0o644); err != nil {
				loi = append(loi, "ghi XML: "+err.Error())
			} else {
				hd.TepXML = p
				if err := DocXMLHoaDon(b, hd); err != nil {
					loi = append(loi, err.Error())
				}
			}
		}
	}
	if hd.LinkPDF != "" {
		b, ct, err := taiTep(hd.LinkPDF)
		if err != nil {
			loi = append(loi, "PDF: "+err.Error())
		} else if !bytes.HasPrefix(b, []byte("%PDF")) && !strings.Contains(strings.ToLower(ct), "pdf") {
			loi = append(loi, "PDF: máy chủ không trả tệp PDF (mở link tra cứu để tải thủ công)")
		} else {
			p := filepath.Join(thuMuc, tenTepHD(hd, ".pdf"))
			if err := os.WriteFile(p, b, 0o644); err == nil {
				hd.TepPDF = p
			}
		}
	}
	if len(loi) > 0 {
		hd.Loi = strings.Join(loi, "; ")
		if hd.TrangThai != "da-doc" {
			hd.TrangThai = "loi"
		}
		return errors.New(hd.Loi)
	}
	if hd.TrangThai != "da-doc" {
		hd.TrangThai = "da-tai"
	}
	hd.Loi = ""
	return nil
}

// ---------- Everything ----------

type ketQuaTep struct {
	Duong  string `json:"duong"`
	KichCo int64  `json:"kichCo"`
	SuaLuc string `json:"suaLuc"`
}

// TimEverything hỏi Everything HTTP server (Tools → Options → HTTP Server).
func TimEverything(baseURL, truyVan string, toiDa int) ([]ketQuaTep, error) {
	u := strings.TrimRight(baseURL, "/") + "/?search=" + url.QueryEscape(truyVan) +
		"&json=1&path_column=1&size_column=1&date_modified_column=1&count=" + strconv.Itoa(toiDa)
	c := &http.Client{Timeout: 20 * time.Second}
	resp, err := c.Get(u)
	if err != nil {
		return nil, fmt.Errorf("không kết nối được Everything tại %s (bật Tools → Options → HTTP Server): %v", baseURL, err)
	}
	defer resp.Body.Close()
	var ra struct {
		Results []struct {
			Type string `json:"type"`
			Name string `json:"name"`
			Path string `json:"path"`
			Size string `json:"size"`
			Date string `json:"date_modified"`
		} `json:"results"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&ra); err != nil {
		return nil, fmt.Errorf("Everything trả về dữ liệu lạ: %v", err)
	}
	var ket []ketQuaTep
	for _, r := range ra.Results {
		if r.Type != "file" {
			continue
		}
		kc, _ := strconv.ParseInt(r.Size, 10, 64)
		ket = append(ket, ketQuaTep{Duong: filepath.Join(r.Path, r.Name), KichCo: kc, SuaLuc: r.Date})
	}
	return ket, nil
}

// TimES dùng es.exe (Everything command line) nếu có trong PATH.
func TimES(truyVan string, toiDa int) ([]ketQuaTep, error) {
	out, err := exec.Command("es.exe", "-n", strconv.Itoa(toiDa), truyVan).Output()
	if err != nil {
		return nil, fmt.Errorf("es.exe: %v", err)
	}
	var ket []ketQuaTep
	for _, l := range strings.Split(strings.ReplaceAll(string(out), "\r", ""), "\n") {
		if l = strings.TrimSpace(l); l != "" {
			ket = append(ket, ketQuaTep{Duong: l})
		}
	}
	return ket, nil
}

// QuetThuMuc tìm .xml/.pdf/.zip trong các thư mục (tối đa 6 cấp, 20.000 tệp).
func QuetThuMuc(thuMuc []string) []ketQuaTep {
	var ket []ketQuaTep
	for _, tm := range thuMuc {
		tm = strings.TrimSpace(tm)
		if tm == "" {
			continue
		}
		goc := strings.Count(filepath.Clean(tm), string(filepath.Separator))
		n := 0
		filepath.WalkDir(tm, func(p string, d os.DirEntry, err error) error {
			if err != nil {
				return nil
			}
			if d.IsDir() {
				if strings.Count(p, string(filepath.Separator))-goc > 6 || strings.HasPrefix(d.Name(), ".") || strings.EqualFold(d.Name(), "node_modules") {
					return filepath.SkipDir
				}
				return nil
			}
			n++
			if n > 20000 {
				return filepath.SkipAll
			}
			switch strings.ToLower(filepath.Ext(p)) {
			case ".xml", ".pdf", ".zip":
				info, _ := d.Info()
				k := ketQuaTep{Duong: p}
				if info != nil {
					k.KichCo, k.SuaLuc = info.Size(), info.ModTime().Format("02/01/2006 15:04")
				}
				ket = append(ket, k)
			}
			return nil
		})
	}
	return ket
}

// DocTepHoaDon mở tệp .xml/.zip, trả về hoá đơn nếu đúng của NCC đang lọc.
func DocTepHoaDon(duong, locNCC, mst string) (*HoaDon, error) {
	b, err := os.ReadFile(duong)
	if err != nil {
		return nil, err
	}
	if len(b) > 30<<20 {
		return nil, errors.New("tệp quá lớn")
	}
	hd := &HoaDon{Nguon: "thu-muc", TrangThai: "moi", TepXML: duong}
	if err := DocXMLHoaDon(b, hd); err != nil {
		return nil, err
	}
	if !khopNCC(hd, locNCC, mst) {
		return nil, errors.New("không phải NCC đang lọc: " + hd.NCC)
	}
	return hd, nil
}

// khopNCC: locNCC là danh sách tên (không dấu) cách nhau dấu phẩy; mst là danh sách MST cách nhau dấu phẩy.
func khopNCC(hd *HoaDon, locNCC, mst string) bool {
	if dsMST := tachDS(mst); len(dsMST) > 0 && hd.MST != "" {
		for _, m := range dsMST {
			if hd.MST == m {
				return true
			}
		}
		return false // MST có mà không khớp: từ chối, không xét tên
	}
	ds := tachDS(locNCC)
	if len(ds) == 0 {
		return true
	}
	ten := strings.ToUpper(boDau(hd.NCC))
	for _, l := range ds {
		if strings.Contains(ten, strings.ToUpper(boDau(l))) {
			return true
		}
	}
	return false
}

func tachDS(s string) []string {
	var ket []string
	for _, x := range strings.FieldsFunc(s, func(r rune) bool { return r == ',' || r == ';' || r == '|' }) {
		if x = strings.TrimSpace(x); x != "" {
			ket = append(ket, x)
		}
	}
	return ket
}

// ---------- Danh sách link từ Bridge (phiên Claude Cloud ghi) ----------

type linkHDDT struct {
	NCC, So, KyHieu, MauSo, NgayLap, MaCQT, EmailNgay, LinkTraCuu, MaTraCuu, LinkXML, LinkPDF string
}

func DocDanhSachLink(b []byte) ([]*HoaDon, error) {
	var ds []linkHDDT
	if err := json.Unmarshal(b, &ds); err != nil {
		var boc struct{ HoaDon []linkHDDT }
		if err2 := json.Unmarshal(b, &boc); err2 != nil {
			return nil, err
		}
		ds = boc.HoaDon
	}
	var ket []*HoaDon
	for _, l := range ds {
		if l.So == "" {
			continue
		}
		if l.MaTraCuu != "" && l.LinkXML == "" && strings.Contains(l.LinkTraCuu, "meinvoice") {
			l.LinkXML = "https://www.meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=" + l.MaTraCuu
			l.LinkPDF = "https://www.meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=pdf&Code=" + l.MaTraCuu
		}
		ms, kh := tachKyHieu(strings.ToUpper(strings.TrimSpace(l.KyHieu)))
		if l.MauSo == "" {
			l.MauSo = ms
		}
		ket = append(ket, &HoaDon{So: strings.TrimLeft(l.So, "0"), KyHieu: kh, MauSo: l.MauSo, NCC: l.NCC,
			NgayLap: l.NgayLap, MaCQT: l.MaCQT, EmailNgay: l.EmailNgay, LinkTraCuu: l.LinkTraCuu, MaTraCuu: l.MaTraCuu, LinkXML: l.LinkXML, LinkPDF: l.LinkPDF,
			Nguon: "bridge", TrangThai: "moi"})
	}
	return ket, nil
}

// TimTepLinkTrenBridge liệt kê hddt-links-*.json trong thư mục Bridge, mới nhất trước.
func TimTepLinkTrenBridge(thuMuc string) []string {
	m, _ := filepath.Glob(filepath.Join(thuMuc, "hddt-links-*.json"))
	sort.Sort(sort.Reverse(sort.StringSlice(m)))
	return m
}

// ---------- Đối chiếu dòng hoá đơn với báo giá ----------

var reModelHD = regexp.MustCompile(`\b([A-Z]\d{2,3}[A-Z]?|S\d{2}\s?(?:FE|ULTRA|\+)?|TAB\s?[AS]\d{1,2}|Z\s?FOLD\s?\d|Z\s?FLIP\s?\d)\b`)
var reSKU = regexp.MustCompile(`^[XFRLTA]\d{3}[A-Z]?$`)
var reRomHD = regexp.MustCompile(`\b(\d{1,2})\s*G?B?\s*/\s*(\d{2,4})\s*G?B?\b|\b(64|128|256|512|1024)\s*GB?\b`)

// DoiChieu tìm dòng báo giá gần ngày hoá đơn nhất, cùng model (ưu tiên mã SKU X133/F966/A076…),
// và cùng cấu hình nếu hoá đơn ghi.
func DoiChieu(d DongHD, ngayHD string, baoGia []DongGia) *DongGia {
	ten := strings.ToUpper(boDau(d.Ten))
	var ungVien []string
	for _, m := range reModelHD.FindAllStringSubmatch(ten, -1) {
		x := strings.ReplaceAll(m[1], " ", "")
		if reSKU.MatchString(x) {
			ungVien = append([]string{x}, ungVien...) // mã SKU lên đầu
		} else {
			ungVien = append(ungVien, x)
		}
	}
	rom := ""
	if r := reRomHD.FindStringSubmatch(ten); r != nil {
		if r[2] != "" {
			rom = r[1] + "/" + r[2]
		} else {
			rom = r[3]
		}
	}
	for _, model := range ungVien {
		var tot *DongGia
		for i := range baoGia {
			g := &baoGia[i]
			if g.SLMin != 1 {
				continue
			}
			if !strings.EqualFold(g.Model, model) && !coModel(g.TenHang, model) {
				continue
			}
			if rom != "" && g.CauHinh != "" && g.CauHinh != rom && !strings.HasSuffix(g.CauHinh, "/"+rom) && !strings.HasSuffix(rom, "/"+g.CauHinh) {
				continue
			}
			if tot == nil || abs64(ngayKhoaInt(g.Ngay)-ngayKhoaInt(ngayHD)) < abs64(ngayKhoaInt(tot.Ngay)-ngayKhoaInt(ngayHD)) {
				tot = g
			}
		}
		if tot != nil {
			return tot
		}
	}
	return nil
}

// coModel: tên báo giá có đúng mã model (so cả từ, "A07S" không khớp "A07").
func coModel(tenHang, model string) bool {
	for _, m := range reModelHD.FindAllStringSubmatch(strings.ToUpper(boDau(tenHang)), -1) {
		if strings.ReplaceAll(m[1], " ", "") == model {
			return true
		}
	}
	return false
}

func ngayKhoaInt(n string) int64 { v, _ := strconv.ParseInt(ngayKhoa(n), 10, 64); return v }
func abs64(x int64) int64 {
	if x < 0 {
		return -x
	}
	return x
}
