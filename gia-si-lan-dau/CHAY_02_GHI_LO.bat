@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === XEM TRUOC (khong ghi gi) ===
python ghi_lo_gia_si.py
if errorlevel 1 ( echo DUNG: xem truoc that bai, khong ghi. & pause & exit /b 1 )
echo.
echo === GHI THAT: se hoi go chu GHI ===
python ghi_lo_gia_si.py --ghi
echo.
echo Xong. Doc file log va file Ket Qua Ghi Lo Gia Si Lan Dau *.xlsx.
pause
