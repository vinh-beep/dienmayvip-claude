@echo off
rem Bam dup: go tac vu giu phien Remote Control va tra lai cai dat Windows Update nhu cu.
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 ( powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b )
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Giu-Phien-RC.ps1" -GoCai
pause
