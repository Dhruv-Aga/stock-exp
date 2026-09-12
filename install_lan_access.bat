@echo off
echo ============================================
echo  Bharat Scout - same-Wi-Fi access
echo ============================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" lan
echo.
pause
