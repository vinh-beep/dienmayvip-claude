package main

// Kho dữ liệu: 1 tệp JSON cạnh app (du-lieu/bao-gia-ncc.json), ghi tạm rồi đổi tên,
// sao lưu bản cũ vào du-lieu/sao-luu/ trước mỗi lần ghi.

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

type Kho struct {
	mu      sync.Mutex
	duong   string
	Dong    []DongGia   `json:"dong"`
	MaCuoi  int64       `json:"maCuoi"`
	HoaDon  []*HoaDon   `json:"hoaDon"`
	CauHinh CauHinhHDDT `json:"cauHinh"`
}

func MoKho(thuMuc string) (*Kho, error) {
	if err := os.MkdirAll(filepath.Join(thuMuc, "sao-luu"), 0o755); err != nil {
		return nil, err
	}
	k := &Kho{duong: filepath.Join(thuMuc, "bao-gia-ncc.json"), CauHinh: cauHinhMacDinh()}
	b, err := os.ReadFile(k.duong)
	if errors.Is(err, os.ErrNotExist) {
		return k, nil
	}
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(b, k); err != nil {
		return nil, err
	}
	if k.CauHinh.EverythingURL == "" {
		k.CauHinh = cauHinhMacDinh()
	}
	return k, nil
}

func (k *Kho) ghi() error {
	if cu, err := os.ReadFile(k.duong); err == nil {
		ten := "bao-gia-ncc-" + time.Now().Format("20060102-150405") + ".json"
		_ = os.WriteFile(filepath.Join(filepath.Dir(k.duong), "sao-luu", ten), cu, 0o644)
	}
	b, err := json.MarshalIndent(k, "", " ")
	if err != nil {
		return err
	}
	tam := k.duong + ".tmp"
	if err := os.WriteFile(tam, b, 0o644); err != nil {
		return err
	}
	return os.Rename(tam, k.duong)
}

func (k *Kho) TatCa() []DongGia {
	k.mu.Lock()
	defer k.mu.Unlock()
	ket := make([]DongGia, len(k.Dong))
	copy(ket, k.Dong)
	sort.SliceStable(ket, func(i, j int) bool { // mới nhất trên cùng
		if a, b := ngayKhoa(ket[i].Ngay), ngayKhoa(ket[j].Ngay); a != b {
			return a > b
		}
		return ket[i].ID > ket[j].ID
	})
	return ket
}

// ngayKhoa đổi dd/mm/yyyy -> yyyymmdd để so sánh.
func ngayKhoa(ngay string) string {
	if len(ngay) == 10 && ngay[2] == '/' && ngay[5] == '/' {
		return ngay[6:] + ngay[3:5] + ngay[:2]
	}
	return ngay
}

func (k *Kho) Them(ds []DongGia) (int, error) {
	k.mu.Lock()
	defer k.mu.Unlock()
	luc := time.Now().Format("02/01/2006 15:04")
	for _, d := range ds {
		if d.DonGia <= 0 || d.TenHang == "" {
			continue
		}
		k.MaCuoi++
		d.ID = k.MaCuoi
		d.TaoLuc = luc
		if d.LoaiHang != DaKich {
			if d.LoaiHang != ChuaKich {
				d.LoaiHang = ChuaKich
			}
		}
		k.Dong = append(k.Dong, d)
	}
	return len(ds), k.ghi()
}

func (k *Kho) Sua(d DongGia) error {
	k.mu.Lock()
	defer k.mu.Unlock()
	for i := range k.Dong {
		if k.Dong[i].ID == d.ID {
			cu := k.Dong[i]
			cu.TenHang, cu.Model, cu.Mau, cu.LoaiHang = d.TenHang, d.Model, d.Mau, d.LoaiHang
			cu.SLMin, cu.DonGia, cu.GhiChu, cu.Ngay, cu.NCC = d.SLMin, d.DonGia, d.GhiChu, d.Ngay, d.NCC
			k.Dong[i] = cu
			return k.ghi()
		}
	}
	return errors.New("không thấy dòng")
}

func (k *Kho) Xoa(ids map[int64]bool) (int, error) {
	k.mu.Lock()
	defer k.mu.Unlock()
	var giu []DongGia
	n := 0
	for _, d := range k.Dong {
		if ids[d.ID] {
			n++
			continue
		}
		giu = append(giu, d)
	}
	k.Dong = giu
	return n, k.ghi()
}

// ---------- Hoá đơn ----------

func (k *Kho) CacHoaDon() []*HoaDon {
	k.mu.Lock()
	defer k.mu.Unlock()
	ket := make([]*HoaDon, len(k.HoaDon))
	copy(ket, k.HoaDon)
	sort.SliceStable(ket, func(i, j int) bool { // mới nhất trên cùng
		a, b := ngayKhoa(ket[i].NgayLap), ngayKhoa(ket[j].NgayLap)
		if a == "" {
			a = ngayKhoa(ket[i].EmailNgay)
		}
		if b == "" {
			b = ngayKhoa(ket[j].EmailNgay)
		}
		if a != b {
			return a > b
		}
		return ket[i].ID > ket[j].ID
	})
	return ket
}

// ThemHoaDon gộp theo (Ký hiệu, Số): có rồi thì bổ sung link/tệp còn thiếu. Trả về số thêm mới.
func (k *Kho) ThemHoaDon(ds []*HoaDon) (int, error) {
	k.mu.Lock()
	defer k.mu.Unlock()
	luc := time.Now().Format("02/01/2006 15:04")
	moi := 0
	for _, hd := range ds {
		if hd.So == "" {
			continue
		}
		if hd.Dong == nil {
			hd.Dong = []DongHD{}
		}
		var cu *HoaDon
		for _, x := range k.HoaDon {
			if x.So == hd.So && (x.KyHieu == hd.KyHieu || x.KyHieu == "" || hd.KyHieu == "") {
				cu = x
				break
			}
		}
		if cu == nil {
			k.MaCuoi++
			hd.ID = k.MaCuoi
			hd.TaoLuc = luc
			k.HoaDon = append(k.HoaDon, hd)
			moi++
			continue
		}
		gop := func(dst *string, src string) {
			if *dst == "" && src != "" {
				*dst = src
			}
		}
		gop(&cu.KyHieu, hd.KyHieu)
		gop(&cu.MauSo, hd.MauSo)
		gop(&cu.NgayLap, hd.NgayLap)
		gop(&cu.NCC, hd.NCC)
		gop(&cu.MST, hd.MST)
		gop(&cu.EmailNgay, hd.EmailNgay)
		gop(&cu.LinkTraCuu, hd.LinkTraCuu)
		gop(&cu.MaTraCuu, hd.MaTraCuu)
		gop(&cu.LinkXML, hd.LinkXML)
		gop(&cu.LinkPDF, hd.LinkPDF)
		gop(&cu.TepXML, hd.TepXML)
		gop(&cu.TepPDF, hd.TepPDF)
		if len(cu.Dong) == 0 && len(hd.Dong) > 0 {
			cu.Dong, cu.TienHang, cu.Thue, cu.TongTT, cu.TrangThai = hd.Dong, hd.TienHang, hd.Thue, hd.TongTT, "da-doc"
		}
	}
	return moi, k.ghi()
}

func (k *Kho) HoaDonTheoID(id int64) *HoaDon {
	k.mu.Lock()
	defer k.mu.Unlock()
	for _, x := range k.HoaDon {
		if x.ID == id {
			return x
		}
	}
	return nil
}

func (k *Kho) LuuHoaDon() error { k.mu.Lock(); defer k.mu.Unlock(); return k.ghi() }

func (k *Kho) XoaHoaDon(id int64) error {
	k.mu.Lock()
	defer k.mu.Unlock()
	for i, x := range k.HoaDon {
		if x.ID == id {
			k.HoaDon = append(k.HoaDon[:i], k.HoaDon[i+1:]...)
			return k.ghi()
		}
	}
	return errors.New("không thấy hoá đơn")
}

func (k *Kho) LuuCauHinh(c CauHinhHDDT) error {
	k.mu.Lock()
	defer k.mu.Unlock()
	k.CauHinh = c
	return k.ghi()
}
func (k *Kho) LayCauHinh() CauHinhHDDT { k.mu.Lock(); defer k.mu.Unlock(); return k.CauHinh }
