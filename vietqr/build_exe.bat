@echo off
REM Dong goi app thanh .exe (chay tren may Windows co Python 3.11+).
cd /d "%~dp0"
python -m pip install -q qrcode pillow pyodbc pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "VietQR Phieu Thu DienmayVIP" app_phieu_thu_qr.py
copy /Y accounts.json dist\ >nul
if exist phieu_ban.config.json copy /Y phieu_ban.config.json dist\ >nul
start /wait "" "dist\VietQR Phieu Thu DienmayVIP.exe" --tu-kiem
if errorlevel 1 (echo TU KIEM LOI & exit /b 1)
echo Xong. File .exe nam trong thu muc dist\
