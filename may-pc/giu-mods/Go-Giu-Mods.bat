@echo off
rem Bam dup: tra settings.json ve nhu truoc khi chay Giu-Mods.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Giu-Mods.ps1" -GoCai
pause
