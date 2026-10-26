// Quản lý báo giá NCC — app chạy tại máy, mở giao diện trong trình duyệt.
// Dữ liệu nằm trong thư mục du-lieu/ cạnh tệp .exe. Không gửi gì ra ngoài máy.
package main

import (
	"embed"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

//go:embed ui
var giaoDien embed.FS

const tenApp = "Quản lý báo giá NCC Khương Việt"

func main() {
	goc, _ := os.Executable()
	thuMuc := filepath.Join(filepath.Dir(goc), "du-lieu")
	if len(os.Args) > 1 {
		thuMuc = os.Args[1]
	}
	_ = os.MkdirAll(thuMuc, 0o755)
	logF, err := os.OpenFile(filepath.Join(thuMuc, "app.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err == nil {
		log.SetOutput(logF)
	}
	kho, err := MoKho(thuMuc)
	if err != nil {
		log.Fatalf("không mở được kho: %v", err)
	}

	ui, _ := fs.Sub(giaoDien, "ui")
	mux := http.NewServeMux()
	mux.Handle("/", http.FileServer(http.FS(ui)))
	mux.HandleFunc("/api/du-lieu", func(w http.ResponseWriter, r *http.Request) {
		traJSON(w, map[string]any{"dong": kho.TatCa(), "thuMuc": thuMuc, "tenApp": tenApp})
	})
	mux.HandleFunc("/api/doc-tin", func(w http.ResponseWriter, r *http.Request) {
		var vao struct{ VanBan, NCC, Ngay string }
		if err := json.NewDecoder(r.Body).Decode(&vao); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		ds := DocVanBan(vao.VanBan, strings.TrimSpace(vao.NCC), strings.TrimSpace(vao.Ngay))
		if ds == nil {
			ds = []DongGia{}
		}
		traJSON(w, ds)
	})
	mux.HandleFunc("/api/luu", func(w http.ResponseWriter, r *http.Request) {
		var ds []DongGia
		if err := json.NewDecoder(r.Body).Decode(&ds); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		n, err := kho.Them(ds)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		traJSON(w, map[string]int{"daLuu": n})
	})
	mux.HandleFunc("/api/sua", func(w http.ResponseWriter, r *http.Request) {
		var d DongGia
		if err := json.NewDecoder(r.Body).Decode(&d); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		if err := kho.Sua(d); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		traJSON(w, map[string]bool{"ok": true})
	})
	mux.HandleFunc("/api/xoa", func(w http.ResponseWriter, r *http.Request) {
		var ids []int64
		if err := json.NewDecoder(r.Body).Decode(&ids); err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		m := map[int64]bool{}
		for _, id := range ids {
			m[id] = true
		}
		n, err := kho.Xoa(m)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		traJSON(w, map[string]int{"daXoa": n})
	})
	dangKyHDDT(mux, kho, thuMuc)
	mux.HandleFunc("/api/xuat-csv", func(w http.ResponseWriter, r *http.Request) {
		ngay, loai := r.URL.Query().Get("ngay"), r.URL.Query().Get("loai")
		ten := "Gia NCC " + time.Now().Format("02 01 2006 15h04p") + ".csv"
		w.Header().Set("Content-Type", "text/csv; charset=utf-8")
		w.Header().Set("Content-Disposition", `attachment; filename="`+ten+`"`)
		w.Write([]byte("\xEF\xBB\xBF")) // BOM cho Excel
		cw := csv.NewWriter(w)
		cw.Write([]string{"NgayBaoGia", "NCC", "NhomHang", "TenHang", "Model", "MauSac", "LoaiHang", "BaoHanh", "SL_Min", "DonGia_VND", "GhiChu"})
		for _, d := range kho.TatCa() {
			if (ngay != "" && d.Ngay != ngay) || (loai != "" && d.LoaiHang != loai) {
				continue
			}
			lh := "Chua kich hoat (chua tham gia CTKM Samsung)"
			if d.LoaiHang == DaKich {
				lh = "Da kich hoat (da tham gia CTKM Samsung)"
			}
			cw.Write([]string{d.Ngay, d.NCC, "Dien thoai", d.TenHang, d.Model, d.Mau, lh, "", strconv.Itoa(d.SLMin), strconv.FormatInt(d.DonGia, 10), d.GhiChu})
		}
		cw.Flush()
	})

	ln, err := net.Listen("tcp", "127.0.0.1:8765")
	if err != nil {
		ln, err = net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			log.Fatal(err)
		}
	}
	url := "http://" + ln.Addr().String() + "/"
	log.Printf("%s chạy tại %s, dữ liệu: %s", tenApp, url, thuMuc)
	fmt.Println(tenApp, "-", url)
	go moTrinhDuyet(url)
	log.Fatal(http.Serve(ln, mux))
}

func traJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(v)
}

func moTrinhDuyet(url string) {
	time.Sleep(300 * time.Millisecond)
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	_ = cmd.Start()
}
