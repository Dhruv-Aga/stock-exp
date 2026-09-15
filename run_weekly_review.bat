@echo off
setlocal
cd /d D:\work\india-trading-bot
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set LOGDIR=D:\work\india-trading-bot\data\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set LOGFILE=%LOGDIR%\weekly_review_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%
set PYTHON=C:\Users\dhruv\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON%" set PYTHON=python
"%PYTHON%" run_weekly_paper.py --review --refresh --email >> "%LOGFILE%" 2>&1
set EXITCODE=%ERRORLEVEL%
echo [%date% %time%] Weekly review exit code %EXITCODE% >> "%LOGFILE%"
endlocal & exit /b %EXITCODE%
