package main

// Số liệu trong kiểm thử là GIẢ.

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const mailMau = ` Fast e-Invoice

Kính gửi *(Dear)*: CÔNG TY TNHH PHÂN PHỐI SỈ & LẺ SẢN PHẨM CÔNG NGHỆ ĐIỆN MÁY VIP

CÔNG TY TNHH THƯƠNG MẠI - DỊCH VỤ KHƯƠNG VIỆT xin gửi cho Quý khách thông tin hóa đơn điện tử *(We would like to send you e-invoice information as below)*:
Số hóa đơn *(Invoice Number)*: * 1158*
Ký hiệu hóa đơn *(Serial Number)*: *C26TKV*
Mẫu số hóa đơn *(Invoice Form)*: *1*

Để tra cứu hóa đơn, quý khách vui lòng truy cập vào đường dẫn *(For more details please access the link)*: [https://einvoice.fast.com.vn](https://einvoice.fast.com.vn/index.aspx?c=AAAAKEY=000780)
Mã số để tra cứu hóa đơn là *(Secure Key for searching)*: *AAAAKEY=000780*
Xem bản thể hiện của hóa đơn điện tử *(To view the printable file)*[ Nhấn vào đây *(click here)*](https://einvoice.fast.com.vn/index.aspx?type=1&c=AAAAKEY=000780&hash=HASH1)
Để tải tệp thông tin hóa đơn điện tử *(To download the XML file)*[ Nhấn vào đây *(click here)*](https://einvoice.fast.com.vn/index.aspx?type=2&c=AAAAKEY=000780&hash=HASH1)
Để tải tệp bản thể hiện của hóa đơn điện tử *(To download the PDF file)*[ Nhấn vào đây *(click here)*](https://einvoice.fast.com.vn/index.aspx?type=3&c=AAAAKEY=000780&hash=HASH1)
`

func TestDocEmailFast(t *testing.T) {
	hd := DocEmailFast(mailMau)
	if hd == nil {
		t.Fatal("không đọc được email")
	}
	if hd.So != "1158" || hd.KyHieu != "C26TKV" || hd.MauSo != "1" || hd.MaTraCuu != "AAAAKEY=000780" {
		t.Errorf("sai: %+v", hd)
	}
	if hd.NCC != "CÔNG TY TNHH THƯƠNG MẠI - DỊCH VỤ KHƯƠNG VIỆT" {
		t.Errorf("NCC sai: %q", hd.NCC)
	}
	if hd.LinkXML != "https://einvoice.fast.com.vn/index.aspx?type=2&c=AAAAKEY=000780&hash=HASH1" || hd.LinkPDF == "" || hd.LinkTraCuu == "" {
		t.Errorf("link sai: %+v", hd)
	}
	if !khopNCC(hd, "KHUONG VIET", "") || khopNCC(hd, "DUY DUC", "") {
		t.Error("lọc NCC sai")
	}
	if DocEmailFast("xin chào, không phải hoá đơn") != nil {
		t.Error("phải trả nil")
	}
}

const xmlMau = `<?xml version="1.0" encoding="UTF-8"?>
<HDon><DLHDon Id="data"><TTChung><KHMSHDon>1</KHMSHDon><KHHDon>C26TKV</KHHDon><SHDon>1158</SHDon><NLap>2026-09-10</NLap></TTChung>
<NDHDon><NBan><Ten>CÔNG TY TNHH THƯƠNG MẠI - DỊCH VỤ KHƯƠNG VIỆT</Ten><MST>0300000000</MST></NBan><NMua><Ten>ĐIỆN MÁY VIP</Ten></NMua>
<DSHHDVu><HHDVu><STT>1</STT><THHDVu>Điện thoại Samsung Galaxy A07 4GB/64GB Đen</THHDVu><DVTinh>Cái</DVTinh><SLuong>2</SLuong><DGia>1000000</DGia><ThTien>2000000</ThTien></HHDVu>
<HHDVu><STT>2</STT><THHDVu>Máy tính bảng Samsung Tab A11 WiFi X133</THHDVu><DVTinh>Cái</DVTinh><SLuong>1</SLuong><DGia>900000.00</DGia><ThTien>900000</ThTien></HHDVu></DSHHDVu>
<TToan><TgTCThue>2900000</TgTCThue><TgTThue>290000</TgTThue><TgTTTBSo>3190000</TgTTTBSo></TToan></NDHDon></DLHDon></HDon>`

func TestDocXMLHoaDon(t *testing.T) {
	hd := &HoaDon{Nguon: "email", LinkXML: "x"}
	if err := DocXMLHoaDon([]byte(xmlMau), hd); err != nil {
		t.Fatal(err)
	}
	if hd.So != "1158" || hd.KyHieu != "C26TKV" || hd.NgayLap != "10/09/2026" || hd.MST != "0300000000" || hd.TongTT != 3190000 || hd.Thue != 290000 {
		t.Errorf("đầu hoá đơn sai: %+v", hd)
	}
	if len(hd.Dong) != 2 || hd.Dong[0].SL != 2 || hd.Dong[0].DonGia != 1000000 || hd.Dong[1].DonGia != 900000 || hd.Dong[1].Ten == "" {
		t.Errorf("dòng sai: %+v", hd.Dong)
	}
	if hd.TrangThai != "da-doc" || hd.LinkXML != "x" {
		t.Errorf("trạng thái/link sai: %+v", hd)
	}
}

func TestDocTepVaLocNCC(t *testing.T) {
	d := t.TempDir()
	p := filepath.Join(d, "hd.xml")
	os.WriteFile(p, []byte(xmlMau), 0o644)
	if _, err := DocTepHoaDon(p, "KHUONG VIET", ""); err != nil {
		t.Fatal(err)
	}
	if _, err := DocTepHoaDon(p, "LONG HUNG", ""); err == nil {
		t.Error("phải loại NCC khác")
	}
	if _, err := DocTepHoaDon(p, "", "0300000000"); err != nil {
		t.Error("MST khớp phải nhận")
	}
	ket := QuetThuMuc([]string{d})
	if len(ket) != 1 || ket[0].Duong != p {
		t.Errorf("quét sai: %+v", ket)
	}
}

func TestDanhSachLink(t *testing.T) {
	ds, err := DocDanhSachLink([]byte(`[{"NCC":"CÔNG TY TNHH THƯƠNG MẠI - DỊCH VỤ KHƯƠNG VIỆT","So":"5117","KyHieu":"c24tkv","EmailNgay":"20/11/2024","LinkXML":"https://x/2","LinkPDF":"https://x/3"},{"NCC":"CÔNG TY TCT","So":"00020588","KyHieu":"1C26TTC","MaTraCuu":"BBFAKE0CODE2","LinkTraCuu":"https://www.meinvoice.vn/tra-cuu/?sc=BBFAKE0CODE2"}]`))
	if err != nil || len(ds) != 2 || ds[0].KyHieu != "C24TKV" || ds[0].Nguon != "bridge" || ds[0].LinkPDF == "" {
		t.Fatalf("sai: %v %+v", err, ds)
	}
	if ds[1].So != "20588" || ds[1].KyHieu != "C26TTC" || ds[1].MauSo != "1" || !strings.Contains(ds[1].LinkXML, "DownloadHandler.ashx?Type=xml&Code=BBFAKE0CODE2") {
		t.Errorf("link MISA sai: %+v", ds[1])
	}
}

func TestDoiChieu(t *testing.T) {
	bg := []DongGia{
		{TenHang: "A07 (4/64)", CauHinh: "4/64", Ngay: "13/10/2026", SLMin: 1, DonGia: 1100000, LoaiHang: DaKich},
		{TenHang: "A07 (4/64)", CauHinh: "4/64", Ngay: "06/10/2026", SLMin: 1, DonGia: 1050000, LoaiHang: DaKich},
		{TenHang: "A07 (4/64)", CauHinh: "4/64", Ngay: "06/10/2026", SLMin: 10, DonGia: 1000000, LoaiHang: DaKich},
		{TenHang: "Tab A11 4G (4/64)", Model: "X135", CauHinh: "4/64", Ngay: "13/10/2026", SLMin: 1, DonGia: 900000},
		{TenHang: "Tab A11 Wifi (4/64)", Model: "X133", CauHinh: "4/64", Ngay: "13/10/2026", SLMin: 1, DonGia: 800000},
	}
	bg = append([]DongGia{{TenHang: "A07S (4/64)", CauHinh: "4/64", Ngay: "08/10/2026", SLMin: 1, DonGia: 1200000, LoaiHang: DaKich}}, bg...)
	g := DoiChieu(DongHD{Ten: "Điện thoại Samsung Galaxy A07 4GB/64GB Đen"}, "08/10/2026", bg)
	if g != nil && g.TenHang == "A07S (4/64)" {
		t.Error("A07 khớp nhầm A07S")
	}
	if g == nil || g.Ngay != "06/10/2026" || g.SLMin != 1 {
		t.Errorf("đối chiếu A07 sai: %+v", g)
	}
	g = DoiChieu(DongHD{Ten: "Máy tính bảng Samsung Tab A11 WiFi X133"}, "10/09/2026", bg)
	if g == nil || g.Model != "X133" {
		t.Errorf("đối chiếu X133 sai: %+v", g)
	}
	if DoiChieu(DongHD{Ten: "Củ sạc 25W"}, "10/09/2026", bg) != nil {
		t.Error("không có model phải trả nil")
	}
	if !coModel("Tab S10FE (8/128)", "TABS10", false) || coModel("A07S (4/64)", "A07", false) || !coModel("S26 FE (128)", "S26", false) || coModel("S26 FE (128)", "S26", true) ||
		coModel("S26 Ultra", "S2", false) || coModel("Tab S10 FE (8/128)", "S10", false) || !coModel("S26+ (256)", "S26PLUS", true) || !coModel("GalaxyS26FE (128)", "S26FE", true) ||
		!coModel("A17 + ốp lưng (4/128)", "A17", true) || coModel("S26 Ultra (256)", "S26", true) {
		t.Error("coModel sai")
	}
	// Lượt chặt trước: hoá đơn S26 thường lấy quote S26 dù S26 Ultra gần ngày hơn
	bg2 := []DongGia{{TenHang: "S26 (256)", Ngay: "01/09/2026", SLMin: 1, DonGia: 1}, {TenHang: "S26 Ultra (256)", Ngay: "10/09/2026", SLMin: 1, DonGia: 2}, {TenHang: "S26+ (256)", Ngay: "10/09/2026", SLMin: 1, DonGia: 3}}
	if g := DoiChieu(DongHD{Ten: "Galaxy S26 256GB"}, "10/09/2026", bg2); g == nil || g.DonGia != 1 {
		t.Errorf("S26 khớp nhầm biến thể: %+v", g)
	}
	if g := DoiChieu(DongHD{Ten: "Galaxy S26+ 256GB"}, "10/09/2026", bg2); g == nil || g.DonGia != 3 {
		t.Errorf("S26+ sai: %+v", g)
	}
}

func TestDocNoiDungMail(t *testing.T) {
	raw := "From: a@b\r\nSubject: x\r\nContent-Type: multipart/alternative; boundary=\"BB\"\r\n\r\n--BB\r\nContent-Type: text/html; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n<p>S=E1=BB=91 h=C3=B3a =C4=91=C6=A1n: 77 <a href=3D\"https://einvoice.fast.com.vn/index.aspx?type=3D2&amp;c=3DK&amp;hash=3DH\">t=E1=BA=A3i</a></p>\r\n--BB--\r\n"
	txt := DocThu(raw).Text
	if !containsAll(txt, "Số hóa đơn: 77", "https://einvoice.fast.com.vn/index.aspx?type=2&c=K&hash=H") {
		t.Errorf("đọc MIME sai: %q", txt)
	}
	hd := DocEmailFast(txt)
	if hd == nil || hd.So != "77" || hd.LinkXML == "" {
		t.Errorf("email từ HTML sai: %+v", hd)
	}
}

func containsAll(s string, cac ...string) bool {
	for _, c := range cac {
		if !contains(s, c) {
			return false
		}
	}
	return true
}
func contains(s, sub string) bool {
	return len(sub) == 0 || (len(s) >= len(sub) && indexOf(s, sub) >= 0)
}
func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

const mailMISA = `CÔNG TY TNHH ĐẦU TƯ & PHÂN PHỐI THIẾT BỊ VIỄN THÔNG LONG HƯNG thông báo gửi Hóa đơn giá trị gia tăng cho Quý khách
*Kính gửi: Quý khách DIENMAYVIP*
CÔNG TY TNHH ĐẦU TƯ & PHÂN PHỐI THIẾT BỊ VIỄN THÔNG LONG HƯNG xin gửi cho Quý khách Hóa đơn giá trị gia tăng với các thông tin như sau:

* Số: *00002146*
* Ngày: *06/10/2026*
* Ký hiệu: *1C26TLH*
* Mã của cơ quan thuế: *00FAKE00000000000000000000000000CQT*

TRA CỨU ( https://www.meinvoice.vn/tra-cuu/?sc=AAFAKE0CODE1&m=vinh@dienmayvip.com&n=DIENMAYVIP&c=&b=&d=0&t=1&r=1 )
Hoặc truy cập vào đường dẫn https://www.meinvoice.vn/tra-cuu và nhập mã số: *AAFAKE0CODE1*
`

func TestDocEmailMISA(t *testing.T) {
	hd := DocEmail(mailMISA)
	if hd == nil {
		t.Fatal("không đọc được email MISA")
	}
	if hd.So != "2146" || hd.KyHieu != "C26TLH" || hd.MauSo != "1" || hd.NgayLap != "06/10/2026" || hd.MaCQT != "00FAKE00000000000000000000000000CQT" || hd.MaTraCuu != "AAFAKE0CODE1" {
		t.Errorf("sai: %+v", hd)
	}
	if hd.NCC != "CÔNG TY TNHH ĐẦU TƯ & PHÂN PHỐI THIẾT BỊ VIỄN THÔNG LONG HƯNG" {
		t.Errorf("NCC sai: %q", hd.NCC)
	}
	if hd.LinkXML != "https://www.meinvoice.vn/tra-cuu/DownloadHandler.ashx?Type=xml&Code=AAFAKE0CODE1" || hd.LinkTraCuu == "" {
		t.Errorf("link sai: %+v", hd)
	}
	if !khopNCC(hd, "KHUONG VIET, TCT, LONG HUNG, THANH LIEM", "") || khopNCC(hd, "KHUONG VIET, TCT", "") {
		t.Error("lọc nhiều NCC sai")
	}
	// TCT dạng bảng "| Số: 00020588 |"
	tct := "CÔNG TY TNHH THƯƠNG MẠI ĐIỆN TỬ TCT thông báo gửi Hóa đơn giá trị gia tăng cho Quý khách\n| Số: 00020588 |\n| Ngày: 13/10/2026 |\n| Ký hiệu: 1C26TTC |\n[Tra cứu](https://www.meinvoice.vn/tra-cuu/?sc=BBFAKE0CODE2&m=x)\n"
	hd = DocEmail(tct)
	if hd == nil || hd.So != "20588" || hd.KyHieu != "C26TTC" || hd.MauSo != "1" || hd.MaTraCuu != "BBFAKE0CODE2" || !khopNCC(hd, "TCT", "") {
		t.Errorf("TCT sai: %+v", hd)
	}
	// "nhập mã số: *7NF…*" đứng trước dòng Số: không được lấy nhầm số HĐ
	hd = DocEmail("CÔNG TY TNHH X thông báo gửi Hóa đơn\nnhập mã số: *7NFQ0000AAAA*\n* Số: *00000012*\n* Ký hiệu: *1C26TXX*\nhttps://www.meinvoice.vn/tra-cuu/?sc=7NFQ0000AAAA")
	if hd == nil || hd.So != "12" {
		t.Errorf("số HĐ bị nhầm với mã tra cứu: %+v", hd)
	}
	// Thư chỉ có "xin gửi cho Quý khách" (thiếu dòng tiêu đề) vẫn ra tên người bán
	hd = DocEmail("CÔNG TY TNHH Y xin gửi cho Quý khách Hóa đơn giá trị gia tăng\n* Số: *00000013*\nhttps://www.meinvoice.vn/tra-cuu/?sc=ZZFAKE000000")
	if hd == nil || hd.NCC != "CÔNG TY TNHH Y" {
		t.Errorf("tên người bán fallback sai: %+v", hd)
	}
	// MST là cách nhận THÊM (kể cả chi nhánh -001); tên khớp vẫn nhận dù MST không có trong danh sách;
	// chỉ khai MST (không khai tên) thì lọc theo MST
	x := &HoaDon{NCC: "CÔNG TY KHÁC", MST: "999-001"}
	if khopNCC(x, "TCT", "111") || !khopNCC(x, "TCT", "111, 999") || !khopNCC(&HoaDon{NCC: "CÔNG TY TCT", MST: "555"}, "TCT", "111") {
		t.Error("khopNCC theo MST/tên sai")
	}
	if khopNCC(&HoaDon{NCC: "CÔNG TY LẠ", MST: "777"}, "", "111") || !khopNCC(&HoaDon{NCC: "X", MST: "111"}, "", "111") || !khopNCC(&HoaDon{NCC: "X"}, "", "") {
		t.Error("khopNCC chỉ MST sai")
	}
	if ms, kh := tachKyHieu("1C26TLH"); ms != "1" || kh != "C26TLH" {
		t.Error("tachKyHieu sai")
	}
	if _, kh := tachKyHieu("C24TKV"); kh != "C24TKV" {
		t.Error("tachKyHieu Fast sai")
	}
	ds := tachKhoiEmail(mailMISA + "\n\n" + tct + "\n" + mailMau)
	if len(ds) != 3 {
		t.Errorf("tách khối sai: %d", len(ds))
	}
}

func TestDocThuDinhKem(t *testing.T) {
	raw := "From: a@b\r\nSubject: x\r\nContent-Type: multipart/mixed; boundary=\"BB\"\r\n\r\n--BB\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nxin chao\r\n--BB\r\nContent-Type: text/xml; name=\"1C26MTL_00001972.xml\"\r\nContent-Disposition: attachment; filename=\"1C26MTL_00001972.xml\"\r\nContent-Transfer-Encoding: base64\r\n\r\nPEhEb24+PC9IRG9uPg==\r\n--BB--\r\n"
	th := DocThu(raw)
	if th.Text == "" || len(th.DinhKem) != 1 || th.DinhKem[0].Ten != "1C26MTL_00001972.xml" || string(th.DinhKem[0].Du) != "<HDon></HDon>" {
		t.Errorf("đính kèm sai: %+v", th)
	}
}

func TestGopHoaDonKhacCachGhiKyHieu(t *testing.T) {
	k := &Kho{duong: filepath.Join(t.TempDir(), "k.json")}
	n, err := k.ThemHoaDon([]*HoaDon{{So: "2146", KyHieu: "1C26TLH", NCC: "LH", Nguon: "imap"}})
	if err != nil || n != 1 {
		t.Fatal(err, n)
	}
	n, _ = k.ThemHoaDon([]*HoaDon{{So: "2146", KyHieu: "C26TLH", MauSo: "1", NCC: "LH", Nguon: "thu-muc", TepXML: "x.xml"}})
	if n != 0 || len(k.HoaDon) != 1 || k.HoaDon[0].KyHieu != "C26TLH" || k.HoaDon[0].MauSo != "1" || k.HoaDon[0].TepXML != "x.xml" {
		t.Errorf("không gộp được: %d %+v", n, k.HoaDon)
	}
}

func TestDocThuCoTieuDe(t *testing.T) {
	raw := "From: a@b\r\nSubject: =?UTF-8?B?Q8OUTkcgVFkgVENUIGfhu61pIGhvw6EgxJHGoW4gc+G7kSAwMDAyMDU4OA==?=\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nxin chao\r\n"
	th := DocThu(raw)
	if !strings.HasPrefix(th.Text, "CÔNG TY TCT gửi hoá đơn số 00020588") {
		t.Errorf("thiếu tiêu đề: %q", th.Text)
	}
}

func TestSoTienDauNghinVaThapPhan(t *testing.T) {
	cases := map[string]int64{"1,234,567.00": 1234567, "1.234.567,00": 1234567, "1.234.567": 1234567, "3190000": 3190000, "900000.00": 900000, "12,5": 12, "": 0}
	for in, want := range cases {
		if got := soTien(in); got != want {
			t.Errorf("soTien(%q)=%d, muốn %d", in, got, want)
		}
	}
}

func TestMoKhoGiuCauHinh(t *testing.T) {
	d := t.TempDir()
	k, _ := MoKho(d)
	c := k.LayCauHinh()
	c.EverythingURL, c.IMAPMatKhau, c.LocNCC = "", "bi-mat", "TCT"
	if err := k.LuuCauHinh(c); err != nil {
		t.Fatal(err)
	}
	k2, err := MoKho(d)
	if err != nil || k2.LayCauHinh().IMAPMatKhau != "bi-mat" || k2.LayCauHinh().LocNCC != "TCT" {
		t.Errorf("cấu hình bị xoá khi EverythingURL trống: %+v", k2.LayCauHinh())
	}
	k3, _ := MoKho(t.TempDir())
	if k3.LayCauHinh().EverythingURL == "" {
		t.Error("kho mới phải có cấu hình mặc định")
	}
	d4 := t.TempDir() // cấu hình thưa (chỉ MST + mật khẩu) phải được giữ nguyên
	os.WriteFile(filepath.Join(d4, "bao-gia-ncc.json"), []byte(`{"dong":[],"maCuoi":0,"hoaDon":[],"cauHinh":{"mstNCC":"0101","imapMatKhau":"pw"}}`), 0o644)
	k4, _ := MoKho(d4)
	if c := k4.LayCauHinh(); c.MSTNCC != "0101" || c.IMAPMatKhau != "pw" || c.LocNCC != "" {
		t.Errorf("cấu hình thưa bị thay mặc định: %+v", c)
	}
	d5 := t.TempDir() // tệp cũ không có khối cauHinh → mặc định
	os.WriteFile(filepath.Join(d5, "bao-gia-ncc.json"), []byte(`{"dong":[],"maCuoi":0}`), 0o644)
	k5, _ := MoKho(d5)
	if k5.LayCauHinh().LocNCC == "" {
		t.Error("tệp cũ phải nhận cấu hình mặc định")
	}
}

func TestKhopTenPDF(t *testing.T) {
	if !khopTenPDF("1C26MTL_00001972.pdf", "1972", "C26MTL") || khopTenPDF("1C26MTL_00001972.pdf", "1972", "C26TLH") ||
		khopTenPDF("HoaDon_1C26TLH_00001234.pdf", "12", "C26TXX") || khopTenPDF("Hoa don 2126.pdf", "12", "") ||
		!khopTenPDF("Hoa don 12.pdf", "12", "C26TXX") || !khopTenPDF("C26TKV-1158.pdf", "1158", "C26TKV") ||
		khopTenPDF("1C26MTL_00001972.pdf", "26", "C26MTL") || khopTenPDF("1C26MTL_00001972.pdf", "1", "C26MTL") ||
		!khopTenPDF("1C26MTL_00001972.pdf", "1972", "") {
		t.Error("khopTenPDF sai")
	}
}

func TestDoiChieuSKU(t *testing.T) {
	bg := []DongGia{{TenHang: "A076 (4/128)", Model: "A076", CauHinh: "4/128", Ngay: "13/10/2026", SLMin: 1, DonGia: 5},
		{TenHang: "Tab A11 Wifi (4/64)", Model: "X133", CauHinh: "4/64", Ngay: "13/10/2026", SLMin: 1, DonGia: 6}}
	if g := DoiChieu(DongHD{Ten: "Điện thoại Samsung Galaxy A07 4GB/128GB"}, "13/10/2026", bg); g == nil || g.DonGia != 5 {
		t.Errorf("A07 không khớp SKU A076: %+v", g)
	}
	if g := DoiChieu(DongHD{Ten: "Máy tính bảng Samsung Galaxy Tab A11 WiFi 4GB/64GB"}, "13/10/2026", bg); g == nil || g.DonGia != 6 {
		t.Errorf("Tab A11 không khớp X133: %+v", g)
	}
	if skuSangModel("A176") != "A17" || skuSangModel("A176B") != "A17" || skuSangModel("X135") != "TABA11" || skuSangModel("X133B") != "TABA11" || skuSangModel("S26") != "" {
		t.Error("skuSangModel sai")
	}
}
