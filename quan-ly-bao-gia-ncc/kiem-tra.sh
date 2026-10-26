#!/bin/sh
# Cổng kiểm Harness² (luật H11): dừng ngay khi bất kỳ bước nào đỏ. Chạy trước mỗi lần đẩy.
set -eu
cd "$(dirname "$0")"
test -z "$(gofmt -l .)" || { echo "gofmt: có tệp chưa định dạng"; gofmt -l .; exit 1; }
go vet ./...
go test -count=1 ./...
if [ -d ../bang-gia-ncc/tests ]; then (cd .. && python3 -m pytest bang-gia-ncc/tests -q); fi
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -H windowsgui" -o QuanLyBaoGiaNCC-KhuongViet.exe .
echo "CONG KIEM XANH"
