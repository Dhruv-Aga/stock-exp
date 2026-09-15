@echo off
setlocal
cd /d "%~dp0"

set LOGDIR=%~dp0data\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

set LOGFILE=%LOGDIR%\paper_intraday_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set PYTHON=C:\Users\dhruv\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [%date% %time%] Starting intraday paper session >> "%LOGFILE%"
"%PYTHON%" "%~dp0run_paper_intraday.py" >> "%LOGFILE%" 2>&1
set EXITCODE=%ERRORLEVEL%

if %EXITCODE%==0 (
    echo [%date% %time%] Intraday paper OK >> "%LOGFILE%"
) else (
    echo [%date% %time%] Intraday paper FAILED exit code %EXITCODE% >> "%LOGFILE%"
)

endlocal & exit /b %EXITCODE%
