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
	mu     sync.Mutex
	duong  string
	Dong   []DongGia `json:"dong"`
	MaCuoi int64     `json:"maCuoi"`
}

func MoKho(thuMuc string) (*Kho, error) {
	if err := os.MkdirAll(filepath.Join(thuMuc, "sao-luu"), 0o755); err != nil {
		return nil, err
	}
	k := &Kho{duong: filepath.Join(thuMuc, "bao-gia-ncc.json")}
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
