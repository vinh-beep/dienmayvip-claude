@echo off
rem Bam dup: dang ky tu mo lai phien Remote Control khi dang nhap, roi mo ngay bay gio.
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 ( powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b )
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Giu-Phien-RC.ps1" -CaiLich
start "" notepad "%~dp0thu-muc-phien.txt"
echo Sua danh sach thu muc trong Notepad va luu lai. Trong 5 phut cac phien se tu mo.
pause
