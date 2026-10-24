@echo off
cd /d "%~dp0"
go test ./... || exit /b 1
set GOOS=windows
set GOARCH=amd64
set CGO_ENABLED=0
go build -trimpath -ldflags "-s -w -H windowsgui" -o QuanLyBaoGiaNCC-KhuongViet.exe .
echo Da build: %~dp0QuanLyBaoGiaNCC-KhuongViet.exe
