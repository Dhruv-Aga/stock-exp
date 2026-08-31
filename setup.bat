@echo off
echo ============================================
echo  India Trading Bot - First-time setup
echo ============================================
cd /d D:\work\india-trading-bot

echo.
echo Installing Python packages...
pip install -r requirements.txt -q

echo.
python check_setup.py

echo.
pause
