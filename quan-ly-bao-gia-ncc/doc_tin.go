package main

// Đọc tin bảng giá NCC dán từ Telegram (kiểu MD Samsung) thành các dòng giá.
// Bản Go của bang-gia-ncc/doc_bang_gia_telegram.py; Go không có lookbehind nên
// mẫu giá bắt thêm ký tự biên.

import (
	"regexp"
	"strconv"
	"strings"
)

type DongGia struct {
	ID       int64  `json:"id"`
	Ngay     string `json:"ngay"`     // dd/mm/yyyy
	NCC      string `json:"ncc"`      // tên NCC
	TenHang  string `json:"tenHang"`  // kèm (RAM/ROM)
	Model    string `json:"model"`    // mã Samsung: A076, X135, F966...
	CauHinh  string `json:"cauHinh"`  // 4/128 hoặc 256
	Mau      string `json:"mau"`      // Den/Xanh/...
	LoaiHang string `json:"loaiHang"` // DaKich | ChuaKich
	SLMin    int    `json:"slMin"`    // 1 = giá lẻ; n = bậc số lượng; 0 = NCC không ghi số
	DonGia   int64  `json:"donGia"`   // VND
	GhiChu   string `json:"ghiChu"`
	DongGoc  string `json:"dongGoc"` // dòng Telegram nguyên văn
	TaoLuc   string `json:"taoLuc"`  // thời điểm lưu
}

const (
	DaKich   = "DaKich"   // đã kích hoạt = đã tham gia CTKM Samsung
	ChuaKich = "ChuaKich" // chưa kích hoạt = chưa tham gia CTKM Samsung
)

// Màu: khoá không dấu + các cách viết CÓ DẤU đúng. Một từ chỉ được coi là màu khi nó viết đúng
// dấu (đen, bạc, hồng, tím, trắng) hoặc hoàn toàn không dấu (Den, Bac) — để "đến", "bậc", "hỏng",
// "tìm", "trạng" không bị nhận nhầm là màu.
var mauChuan = []struct {
	khoa, chuan string
	coDau       []string
}{
	{"xanh duong", "Xanh duong", []string{"xanh dương"}}, {"x duong", "Xanh duong", []string{"x dương"}},
	{"x blue", "Xanh duong", nil}, {"xanh blue", "Xanh duong", nil}, {"blue", "Xanh duong", nil},
	{"xanh la", "Xanh la", []string{"xanh lá"}}, {"x la", "Xanh la", []string{"x lá"}},
	{"xanh", "Xanh", nil}, {"den", "Den", []string{"đen"}}, {"tim", "Tim", []string{"tím"}},
	{"trang", "Trang", []string{"trắng"}}, {"xam", "Xam", []string{"xám"}},
	{"bac", "Bac", []string{"bạc"}}, {"pink", "Hong", nil}, {"hong", "Hong", []string{"hồng"}}, {"vang", "Vang", []string{"vàng"}},
}

func laMau(tuGoc, khoa string, coDau []string) bool {
	t := strings.ToLower(strings.TrimSpace(tuGoc))
	if t == khoa && boDau(t) == t { // viết không dấu hoàn toàn
		return true
	}
	for _, d := range coDau {
		if t == d {
			return true
		}
	}
	return false
}

var (
	reGia     = regexp.MustCompile(`(?i)(^|[^\w/])(\d{1,3}(?:\.\d{3})+k?|\d{2,6}k)([^\w/]|$)`)
	reSL      = regexp.MustCompile(`(?i)\bsl\s*:?\s*(\d+)?\s*c?\b`)
	reSLTruoc = regexp.MustCompile(`(?i)\bsl\s*:?\s*(\d+)\s*c?\s*:?\s*$`)
	reSLIt    = regexp.MustCompile(`(?i)\bsl\s*(ít|it)\b`)
	reRamRom  = regexp.MustCompile(`(?i)\(?\s*(2|3|4|6|8|12|16)\s*G?B?\s*/\s*(32|64|126|128|256|512|1024)\s*G?B?\s*\)?`)
	reRom     = regexp.MustCompile(`(?i)\(\s*(32|64|126|128|256|512|1024)\s*\)|\b(32|64|126|128|256|512|1024)\s*G\b|\b(32|64|126|128|256|512|1024)\b`)
	reMa      = regexp.MustCompile(`\b([A-Z]\d{3}[A-Z]?)\b`)
	reKhoang  = regexp.MustCompile(`\s+`)
	reTachGC  = regexp.MustCompile(`[-.;:()]`)
	reDauCau  = regexp.MustCompile(`[().,:;*/-]`)
)

var mangTag = map[string]bool{"4G": true, "5G": true, "LTE": true, "WIFI": true, "4G LTE": true}

// boDau bỏ dấu tiếng Việt (đủ cho tên hàng/màu trong tin NCC).
func boDau(s string) string {
	var b strings.Builder
	for _, r := range s {
		if t, ok := bangDau[r]; ok {
			b.WriteString(t)
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

var bangDau = map[rune]string{}

func init() {
	nhom := map[string]string{
		"a": "àáạảãâầấậẩẫăằắặẳẵ", "e": "èéẹẻẽêềếệểễ", "i": "ìíịỉĩ", "o": "òóọỏõôồốộổỗơờớợởỡ",
		"u": "ùúụủũưừứựửữ", "y": "ỳýỵỷỹ", "d": "đ",
		"A": "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴ", "E": "ÈÉẸẺẼÊỀẾỆỂỄ", "I": "ÌÍỊỈĨ", "O": "ÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠ",
		"U": "ÙÚỤỦŨƯỪỨỰỬỮ", "Y": "ỲÝỴỶỸ", "D": "Đ",
	}
	for goc, cac := range nhom {
		for _, r := range cac {
			bangDau[r] = goc
		}
	}
}

func gon(s string) string { return strings.TrimSpace(reKhoang.ReplaceAllString(s, " ")) }

// DocGia: "5.360k" -> 5360000; "16.890" -> 16890000; "990k" -> 990000.
func DocGia(chuoi string) int64 {
	s := strings.TrimSuffix(strings.ToLower(chuoi), "k")
	n, _ := strconv.ParseInt(strings.ReplaceAll(s, ".", ""), 10, 64)
	if n < 100000 {
		n *= 1000 // NCC ghi theo nghìn đồng
	}
	return n
}

type viTriGia struct {
	bat, ket int
	chuoi    string
}

func timGia(s string) []viTriGia {
	var ket []viTriGia
	for _, m := range reGia.FindAllStringSubmatchIndex(s, -1) {
		ket = append(ket, viTriGia{bat: m[4], ket: m[5], chuoi: s[m[4]:m[5]]})
	}
	return ket
}

func xoaGia(s string) string {
	for _, g := range timGia(s) {
		s = s[:g.bat] + strings.Repeat(" ", g.ket-g.bat) + s[g.ket:]
	}
	return s
}

var reTachTu = regexp.MustCompile(`[().,:;*/\-\s]+`)

// cumMau duyệt các cụm 1–2 từ (gốc, có dấu) và trả về danh sách màu chuẩn; vị trí dùng để xoá khỏi tên.
func cumMau(chuoi string) []string {
	tu := reTachTu.Split(chuoi, -1)
	var ket []string
	them := func(c string) {
		if !chua(ket, c) {
			ket = append(ket, c)
		}
	}
	for i := 0; i < len(tu); i++ {
		if tu[i] == "" {
			continue
		}
		khop := false
		if i+1 < len(tu) && tu[i+1] != "" {
			cum := tu[i] + " " + tu[i+1]
			for _, m := range mauChuan {
				if strings.Contains(m.khoa, " ") && laMau(cum, m.khoa, m.coDau) {
					them(m.chuan)
					khop = true
					i++
					break
				}
			}
		}
		if khop {
			continue
		}
		for _, m := range mauChuan {
			if !strings.Contains(m.khoa, " ") && laMau(tu[i], m.khoa, m.coDau) {
				them(m.chuan)
				break
			}
		}
	}
	return ket
}

func timMau(chuoi string) []string { return cumMau(chuoi) }

// boMau xoá các từ là màu (theo luật laMau) khỏi chuỗi, giữ phần còn lại.
func boMau(chuoi string) string {
	var b strings.Builder
	tu := regexp.MustCompile(`([().,:;*/\-\s]+|[^().,:;*/\-\s]+)`).FindAllString(chuoi, -1)
	for i := 0; i < len(tu); i++ {
		t := tu[i]
		if reTachTu.MatchString(t) {
			b.WriteString(t)
			continue
		}
		// cụm 2 từ
		if i+2 < len(tu) && reTachTu.MatchString(tu[i+1]) && !reTachTu.MatchString(tu[i+2]) {
			cum := t + " " + tu[i+2]
			bo := false
			for _, m := range mauChuan {
				if strings.Contains(m.khoa, " ") && laMau(cum, m.khoa, m.coDau) {
					bo = true
					break
				}
			}
			if bo {
				i += 2
				b.WriteString(" ")
				continue
			}
		}
		bo := false
		for _, m := range mauChuan {
			if !strings.Contains(m.khoa, " ") && laMau(t, m.khoa, m.coDau) {
				bo = true
				break
			}
		}
		if !bo {
			b.WriteString(t)
		} else {
			b.WriteString(" ")
		}
	}
	return gon(boDau(b.String()))
}

// TachDong đọc một dòng "+ ..." thành danh sách dòng giá (mỗi bậc SL một dòng).
func TachDong(dong string) []DongGia {
	goc := strings.TrimSpace(dong)
	if !strings.HasPrefix(goc, "+") {
		return nil
	}
	than := strings.ReplaceAll(goc[1:], "*", " ")
	gias := timGia(than)
	if len(gias) == 0 {
		return nil
	}
	type bac struct {
		sl  int
		gia int64
	}
	slDau := 1
	dauGia := gias[0].bat
	if m := reSLTruoc.FindStringSubmatchIndex(than[:dauGia]); m != nil { // "SL 5: 1.100k" ngay trước giá đầu
		slDau, _ = strconv.Atoi(than[m[2]:m[3]])
		dauGia = m[0]
	}
	bacs := []bac{{slDau, DocGia(gias[0].chuoi)}}
	for i := 1; i < len(gias); i++ {
		truoc := reSLIt.ReplaceAllString(than[gias[i-1].ket:gias[i].bat], " ") // "SL ít" = sắp hết, không phải bậc
		if m := reSL.FindStringSubmatch(truoc); m != nil {
			sl := 0
			if m[1] != "" {
				sl, _ = strconv.Atoi(m[1])
			}
			bacs = append(bacs, bac{sl, DocGia(gias[i].chuoi)})
		}
	}
	phanTen := than[:dauGia]

	cauHinh := ""
	if m := reRamRom.FindStringSubmatchIndex(phanTen); m != nil {
		cauHinh = phanTen[m[2]:m[3]] + "/" + phanTen[m[4]:m[5]]
		phanTen = phanTen[:m[0]] + " " + phanTen[m[1]:]
	} else if m := reRom.FindStringSubmatchIndex(phanTen); m != nil {
		for _, j := range []int{2, 4, 6} {
			if m[j] >= 0 {
				cauHinh = phanTen[m[j]:m[j+1]]
			}
		}
		phanTen = phanTen[:m[0]] + " " + phanTen[m[1]:]
	}

	ten := phanTen
	mauTho := ""
	if i := strings.Index(phanTen, ":"); i >= 0 {
		ten, mauTho = phanTen[:i], phanTen[i+1:]
	}
	ten = boMau(strings.NewReplacer("(", " ", ")", " ").Replace(ten))
	ten = strings.Trim(gon(strings.ReplaceAll(ten, "/", " ")), " -.,")
	model := ""
	if m := reMa.FindStringSubmatch(strings.ToUpper(ten)); m != nil {
		model = m[1]
		re := regexp.MustCompile(`(?i)\b` + model + `\b`)
		conLai := strings.Trim(gon(re.ReplaceAllString(ten, " ")), " -.,")
		if conLai == "" || mangTag[strings.ToUpper(conLai)] {
			conLai = strings.TrimSpace(model + " " + conLai)
		}
		ten = conLai
	}

	mau := timMau(xoaGia(than))

	var ghiChu []string
	phanSau := reSL.ReplaceAllString(xoaGia(than[dauGia:]), " ") + " " + mauTho
	bo := map[string]bool{"sl": true, "sl it": true}
	for _, m := range mau {
		bo[strings.ToLower(m)] = true
	}
	for _, manh := range reTachGC.Split(boMau(phanSau), -1) {
		manh = strings.Trim(gon(boDau(manh)), " ,")
		if len(manh) >= 3 && !bo[strings.ToLower(manh)] && !chua(ghiChu, manh) {
			ghiChu = append(ghiChu, manh)
		}
	}
	for _, b := range bacs {
		if b.sl == 0 {
			ghiChu = append(ghiChu, "SL: NCC khong ghi so - hoi lai")
			break
		}
	}

	tenDu := ten
	if cauHinh != "" {
		tenDu += " (" + cauHinh + ")"
	}
	var ket []DongGia
	for _, b := range bacs {
		ket = append(ket, DongGia{
			TenHang: tenDu, Model: model, CauHinh: cauHinh, Mau: strings.Join(mau, "/"),
			SLMin: b.sl, DonGia: b.gia, GhiChu: strings.Join(ghiChu, "; "), DongGoc: goc,
		})
	}
	return ket
}

// DocVanBan đọc cả tin: dòng tiêu đề quyết định khối Chưa kích / Đã kích.
func DocVanBan(vanBan, ncc, ngay string) []DongGia {
	loai := ""
	var ket []DongGia
	for _, dong := range strings.Split(vanBan, "\n") {
		thap := strings.ToLower(boDau(dong))
		if !strings.HasPrefix(strings.TrimSpace(dong), "+") {
			t := strings.TrimSpace(thap)
			laTieuDe := len([]rune(t)) <= 80 && !strings.HasPrefix(t, "luu y") && !strings.HasPrefix(t, "chu y") && !strings.HasPrefix(t, "note")
			if laTieuDe && strings.Contains(t, "chua kich") {
				loai = ChuaKich
			} else if laTieuDe && (strings.Contains(t, "kich hoat") || strings.Contains(t, "da kich")) {
				loai = DaKich
			}
			continue
		}
		for _, d := range TachDong(dong) {
			d.LoaiHang, d.NCC, d.Ngay = loai, ncc, ngay
			ket = append(ket, d)
		}
	}
	return ket
}

func chua(ds []string, x string) bool {
	for _, d := range ds {
		if d == x {
			return true
		}
	}
	return false
}
