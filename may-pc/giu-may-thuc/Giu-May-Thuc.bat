@echo off
rem Bam dup de chay. Tu xin quyen Admin roi chay Giu-May-Thuc.ps1 cung thu muc.
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Giu-May-Thuc.ps1"
pause
