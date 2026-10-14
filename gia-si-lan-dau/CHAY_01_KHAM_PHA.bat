@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === KHAM PHA (chi doc, khong ghi gi) ===
python ghi_lo_gia_si.py --kham-pha
echo.
echo Xong. Doc file log trong thu muc log (xem config.json).
pause
