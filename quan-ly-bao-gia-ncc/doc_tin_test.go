package main

// Mọi con số trong kiểm thử là GIẢ, không phải giá NCC thật.

import "testing"

func TestDocGia(t *testing.T) {
	cases := map[string]int64{"1.234k": 1234000, "12.345": 12345000, "555k": 555000, "1.020k": 1020000}
	for in, want := range cases {
		if got := DocGia(in); got != want {
			t.Errorf("DocGia(%q)=%d, muốn %d", in, got, want)
		}
	}
}

func TestDongCoBac(t *testing.T) {
	ds := TachDong("+ A01 (4/64): Xanh Đen Tim: 1.111k- SL 10: 1.100k")
	if len(ds) != 2 || ds[0].SLMin != 1 || ds[0].DonGia != 1111000 || ds[1].SLMin != 10 || ds[1].DonGia != 1100000 {
		t.Fatalf("bậc SL sai: %+v", ds)
	}
	if ds[0].TenHang != "A01 (4/64)" || ds[0].Mau != "Xanh/Den/Tim" {
		t.Errorf("tên/màu sai: %+v", ds[0])
	}
}

func TestSoTronKhongPhaiGia(t *testing.T) {
	ds := TachDong("+ S99ultra (256): 22.222k (đen,trắng, tím)")
	if len(ds) != 1 || ds[0].DonGia != 22222000 || ds[0].CauHinh != "256" || ds[0].TenHang != "S99ultra (256)" {
		t.Fatalf("sai: %+v", ds)
	}
}

func TestMaModel(t *testing.T) {
	ds := TachDong("+ Zfold 9 - F999 256G: 33.333k . Đen")
	if ds[0].TenHang != "Zfold 9 (256)" || ds[0].Model != "F999" || ds[0].Mau != "Den" {
		t.Errorf("sai: %+v", ds[0])
	}
	ds = TachDong("+ X998 4G( 4/64): Bạc Xám : 4.444k")
	if ds[0].TenHang != "X998 4G (4/64)" || ds[0].Model != "X998" {
		t.Errorf("sai: %+v", ds[0])
	}
	ds = TachDong("+ A001 (4/128): *1.234k. Đen. Xanh*Update mới*")
	if ds[0].TenHang != "A001 (4/128)" || ds[0].Model != "A001" || ds[0].GhiChu != "Update moi" {
		t.Errorf("sai: %+v", ds[0])
	}
	ds = TachDong("+ Tab Z2 4G ( X998 ) 4G/64G Bạc Xám : *3.333k .SL 5c : 3.300k*")
	if len(ds) != 2 || ds[1].SLMin != 5 || ds[0].TenHang != "Tab Z2 4G (4/64)" {
		t.Errorf("sai: %+v", ds)
	}
}

func TestSLKhongSo(t *testing.T) {
	ds := TachDong("+ B02S( 4/64): Đen Xanh Tím: 2.222k- SL 2.200k")
	if len(ds) != 2 || ds[1].SLMin != 0 || ds[1].GhiChu == "" {
		t.Fatalf("sai: %+v", ds)
	}
}

func TestKhoi(t *testing.T) {
	tin := "Tồn SS *Chưa kích Ngày 01/01/2026*\n+ A1 (4/64): 1.000k Đen\n+ B2 (4/64): 2.000k Đen\nHàng Kích Hoạt\n+ A1 (4/64): 900k- SL 10: 880k\n✅ check ✅\n"
	ds := DocVanBan(tin, "NCC Thu", "01/01/2026")
	if len(ds) != 4 || ds[0].LoaiHang != ChuaKich || ds[2].LoaiHang != DaKich || ds[3].SLMin != 10 || ds[0].NCC != "NCC Thu" {
		t.Fatalf("sai: %+v", ds)
	}
}

func TestMauKhongNhamTuThuong(t *testing.T) {
	ds := TachDong("+ A01 (4/64): 1.111k. Giao đến 15/10, bậc SL 10 hàng hỏng tìm lại")
	if len(ds) != 1 || ds[0].Mau != "" {
		t.Errorf("nhận nhầm màu: %+v", ds)
	}
	ds = TachDong("+ A01 Đen-Xanh: 1.000k")
	if ds[0].Mau != "Den/Xanh" || ds[0].TenHang != "A01" {
		t.Errorf("màu nối gạch sai: %+v", ds[0])
	}
}

func TestSLTruocGiaVaSLIt(t *testing.T) {
	ds := TachDong("+ A01 (4/64): SL 5: 1.100k")
	if len(ds) != 1 || ds[0].SLMin != 5 {
		t.Errorf("SL trước giá sai: %+v", ds)
	}
	ds = TachDong("+ A01 (4/64): 1.111k SL ít - SL 10: 1.000k")
	if len(ds) != 2 || ds[1].SLMin != 10 || ds[0].SLMin != 1 {
		t.Errorf("SL ít bị coi là bậc: %+v", ds)
	}
}

func TestRamRomHopLe(t *testing.T) {
	ds := TachDong("+ Zfold 9/ 5G 256G: 33.333k Đen")
	if ds[0].CauHinh != "256" || ds[0].TenHang != "Zfold 9 5G (256)" {
		t.Errorf("sai: %+v", ds[0])
	}
	ds = TachDong("+ Tab A9 (2025) 64G: 2.000k")
	if ds[0].CauHinh != "64" || ds[0].TenHang != "Tab A9 2025 (64)" {
		t.Errorf("sai: %+v", ds[0])
	}
}

func TestGhiChuKhongDoiKhoi(t *testing.T) {
	ds := DocVanBan("Chưa kích\n+ A01: 1.000k\nLưu ý: máy đã kích hoạt không đổi trả\n+ A02: 1.000k\n", "N", "01/01/2026")
	if len(ds) != 2 || ds[1].LoaiHang != ChuaKich {
		t.Errorf("khối bị đổi bởi ghi chú: %+v", ds)
	}
}
