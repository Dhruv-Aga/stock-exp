$names = @(
    "IndiaTradingBot Morning Report",
    "IndiaTradingBot Evening Report"
)

foreach ($n in $names) {
    $t = Get-ScheduledTask -TaskName $n -ErrorAction Stop
    $t.Settings.DisallowStartIfOnBatteries = $false
    $t.Settings.StopIfGoingOnBatteries = $false
    $t.Settings.StartWhenAvailable = $true
    $t.Settings.ExecutionTimeLimit = "PT1H"
    Set-ScheduledTask -InputObject $t | Out-Null
    Write-Host "[OK] Configured: $n"
}
