@echo off
echo ============================================
echo  Install Bharat Scout boot autostart
echo ============================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" install-autostart
echo.
pause
