@echo off
setlocal
cd /d D:\work\india-trading-bot

set LOGDIR=D:\work\india-trading-bot\data\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

set LOGFILE=%LOGDIR%\report_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%

set PYTHON=C:\Users\dhruv\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [%date% %time%] Starting scheduled report >> "%LOGFILE%"
"%PYTHON%" run_daily_report.py --email >> "%LOGFILE%" 2>&1
set EXITCODE=%ERRORLEVEL%

if %EXITCODE%==0 (
    echo [%date% %time%] Report completed successfully >> "%LOGFILE%"
) else (
    echo [%date% %time%] Report FAILED exit code %EXITCODE% >> "%LOGFILE%"
)

endlocal & exit /b %EXITCODE%
