@echo off
rem Bam dup: chay bao cao 1 lan va dang ky chay lai moi 30 phut.
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 ( powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b )
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Bao-Cao-Suc-Khoe.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Bao-Cao-Suc-Khoe.ps1" -CaiLich
pause
