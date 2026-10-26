@echo off
rem Bam dup: tim nguyen nhan treo khi Restart + cho Windows tu ket thuc chuong trinh treo. Khong khoi dong lai.
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 ( powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b )
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Khoi-Dong-Lai.ps1" -SuaLoi
pause
