@echo off
rem Bam dup: tim nguyen nhan Remote Control rot quanh 00h/12h. Chi doc, khong sua gi.
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 ( powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b )
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Tim-Loi-RC.ps1"
pause
