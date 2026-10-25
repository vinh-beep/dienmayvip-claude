@echo off
rem Bam dup: giu Claude Mods cho moi phien moi (ke ca phien Remote Control tu mo lai).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Giu-Mods.ps1"
pause
