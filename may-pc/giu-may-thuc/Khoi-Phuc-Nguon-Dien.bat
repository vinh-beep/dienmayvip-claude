@echo off
rem Tra lai so do nguon dien da sao luu truoc khi chay Giu-May-Thuc.
cd /d "%~dp0"
if not exist "SaoLuu-NguonDien.pow" ( echo Khong co ban sao luu. & pause & exit /b )
set /p G=<SaoLuu-GUID.txt
rem Khong xoa duoc so do dang dung: chuyen tam sang High performance roi moi xoa va nap lai ban sao luu.
powercfg /setactive SCHEME_MIN
powercfg /delete %G% >nul 2>&1
powercfg /import "%~dp0SaoLuu-NguonDien.pow" %G%
powercfg /setactive %G%
echo Da khoi phuc so do nguon dien %G%.
pause
