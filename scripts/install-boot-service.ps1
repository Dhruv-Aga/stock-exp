#Requires -Version 5.1
# Register Bharat Scout to start on Windows logon (Task Scheduler).
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$taskName = "BharatScoutDevStart"
$devPs1 = Join-Path $RepoRoot "scripts\dev.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$devPs1`" start" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registered scheduled task: $taskName (runs at logon)"
Write-Host "  Start now:  Start-ScheduledTask -TaskName $taskName"
Write-Host "  Remove:     Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
