#!/bin/sh
# Build app Windows 64-bit từ Linux/macOS (không cần cgo).
set -e
cd "$(dirname "$0")"
go test ./...
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -H windowsgui" -o QuanLyBaoGiaNCC-KhuongViet.exe .
echo "Da build: $(pwd)/QuanLyBaoGiaNCC-KhuongViet.exe"
