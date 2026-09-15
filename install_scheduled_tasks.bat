@echo off
echo ============================================
echo  Install India Trading Bot scheduled tasks
echo ============================================

set TASK1=IndiaTradingBot Morning Report
set TASK2=IndiaTradingBot Evening Report
set TASK3=IndiaTradingBot Portfolio Triggers
set TASK4=IndiaTradingBot Intraday Paper
set TASK5=IndiaTradingBot Weekly Review
set SCRIPT=D:\work\india-trading-bot\run_report.bat
set TRIGGER_SCRIPT=D:\work\india-trading-bot\run_triggers.bat
set INTRADAY_SCRIPT=D:\work\india-trading-bot\run_intraday_paper.bat
set WEEKLY_SCRIPT=D:\work\india-trading-bot\run_weekly_review.bat

schtasks /Delete /TN "%TASK1%" /F 2>nul
schtasks /Delete /TN "%TASK2%" /F 2>nul
schtasks /Delete /TN "%TASK3%" /F 2>nul
schtasks /Delete /TN "%TASK4%" /F 2>nul
schtasks /Delete /TN "%TASK5%" /F 2>nul

schtasks /Create /F /SC DAILY /TN "%TASK1%" /TR "%SCRIPT%" /ST 09:15
schtasks /Create /F /SC DAILY /TN "%TASK2%" /TR "%SCRIPT%" /ST 21:15
schtasks /Create /F /SC MINUTE /MO 30 /TN "%TASK3%" /TR "%TRIGGER_SCRIPT%"
schtasks /Create /F /SC MINUTE /MO 30 /TN "%TASK4%" /TR "%INTRADAY_SCRIPT%" /ST 09:15
schtasks /Create /F /SC WEEKLY /D SUN /TN "%TASK5%" /TR "%WEEKLY_SCRIPT%" /ST 18:00

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$names = @('%TASK1%', '%TASK2%', '%TASK3%', '%TASK4%', '%TASK5%');" ^
  "foreach ($n in $names) {" ^
  "  $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue;" ^
  "  if ($t) {" ^
  "    $t.Settings.DisallowStartIfOnBatteries = $false;" ^
  "    $t.Settings.StopIfGoingOnBatteries = $false;" ^
  "    $t.Settings.StartWhenAvailable = $true;" ^
  "    $t.Settings.ExecutionTimeLimit = 'PT1H';" ^
  "    Set-ScheduledTask -InputObject $t | Out-Null;" ^
  "    Write-Host \"[OK] Configured: $n\";" ^
  "  }" ^
  "}"

echo.
echo Testing morning report task...
schtasks /Run /TN "%TASK1%"
timeout /t 20 /nobreak >nul
schtasks /Query /TN "%TASK1%" /V /FO LIST | findstr /I "Last Run Last Result Next Run Status"

echo.
echo Testing evening report task...
schtasks /Run /TN "%TASK2%"
timeout /t 20 /nobreak >nul
schtasks /Query /TN "%TASK2%" /V /FO LIST | findstr /I "Last Run Last Result Next Run Status"

echo.
echo Done. Reports run at 09:15 and 21:15 daily; triggers and intraday paper run every 30 minutes; weekly review runs Sunday at 18:00.
echo Logs: D:\work\india-trading-bot\data\logs\
pause
