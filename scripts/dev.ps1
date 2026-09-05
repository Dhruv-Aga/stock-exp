param(
    [string]$Command = "start"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$devDir = Join-Path $root ".dev"
$agentPid = Join-Path $devDir "agent.pid"
$frontendPid = Join-Path $devDir "frontend.pid"
$kitePid = Join-Path $devDir "kite.pid"
$autostartTaskName = "IndiaTradingBot Dev Server"

function Get-PythonExe {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    throw "python.exe not found on PATH. Install Python or add it to PATH before starting the server."
}

if ($env:HOST_BIND) { $hostBind = $env:HOST_BIND } else { $hostBind = "0.0.0.0" }
if ($env:FRONTEND_PORT) { $frontendPort = [int]$env:FRONTEND_PORT } else { $frontendPort = 8080 }
if ($env:AGENT_API_PORT) { $agentPort = [int]$env:AGENT_API_PORT } else { $agentPort = 8000 }
if ($env:KITE_PROXY_PORT) { $kitePort = [int]$env:KITE_PROXY_PORT } else { $kitePort = 3000 }

function Write-Banner {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "  Bharat Scout / India Trading Bot - local dev"
    Write-Host "============================================================"
}

function Stop-Port {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if (-not $connections) { return }
    foreach ($connection in $connections) {
        try { Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
    }
}

function Remove-PidFile {
    param([string]$PidFile, [string]$Name)
    if (Test-Path $PidFile) {
        $pidValue = (Get-Content -Path $PidFile -TotalCount 1).Trim()
        if ($pidValue -match "^\d+$") {
            try { Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue } catch {}
            Write-Host "Stopped $Name (pid $pidValue)"
        }
        Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Sync-Env {
    if (-not (Test-Path (Join-Path $root ".env"))) {
        Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
        Write-Host "Created .env from .env.example - add your keys before live features work."
    }
    $serverEnv = Join-Path $root "server\.env"
    if (-not (Test-Path $serverEnv)) {
        Copy-Item (Join-Path $root "server\.env.example") $serverEnv
    }
    python (Join-Path $root "scripts\sync_env.py")
}

function Invoke-Setup {
    Write-Banner
    Write-Host "Installing dependencies..."
    python -m pip install --user -r requirements.txt

    $serverPackage = Join-Path $root "server\package.json"
    if (Test-Path $serverPackage) {
        Push-Location (Join-Path $root "server")
        if (Test-Path "package-lock.json") {
            npm ci
        } else {
            npm install
        }
        Pop-Location
    }

    Sync-Env
    Write-Host ""
    Write-Host "Running setup check..."
    python check_setup.py
    Write-Host ""
    Write-Host "Generating paper portfolio snapshot (if possible)..."
    try {
        python scripts/generate_dashboard.py --no-refresh 2>$null | Out-Null
    } catch {
        Write-Host "  (skipped - run again after .env is configured)"
    }
    Write-Host ""
    Write-Host "Setup complete. Run: .\scripts\dev.ps1 start"
}

function Invoke-Start {
    Write-Banner
    New-Item -ItemType Directory -Force -Path $devDir | Out-Null
    Sync-Env

    Remove-PidFile -PidFile $agentPid -Name "agent API"
    Remove-PidFile -PidFile $frontendPid -Name "frontend"
    Remove-PidFile -PidFile $kitePid -Name "Kite proxy"
    Stop-Port -Port $agentPort
    Stop-Port -Port $frontendPort
    if ($env:START_KITE_PROXY -eq "1") { Stop-Port -Port $kitePort }
    Start-Sleep -Seconds 1

    $python = Get-PythonExe
    $pythonDir = Split-Path -Parent $python
    $env:Path = "$pythonDir;$pythonDir\Scripts;" + $env:Path

    Write-Host "Starting agent API on :$agentPort ..."
    $env:HOST_BIND = $hostBind
    $env:AGENT_API_PORT = [string]$agentPort
    $agentLog = Join-Path $devDir "agent.log"
    $agentErr = Join-Path $devDir "agent.err.log"
    $agentProcess = Start-Process -FilePath $python -ArgumentList @("run_agent_api.py") -WorkingDirectory $root -RedirectStandardOutput $agentLog -RedirectStandardError $agentErr -PassThru -WindowStyle Hidden
    Set-Content -Path $agentPid -Value $agentProcess.Id

    Write-Host "Starting frontend on ${hostBind}:$frontendPort ..."
    $env:FRONTEND_PORT = [string]$frontendPort
    $frontendLog = Join-Path $devDir "frontend.log"
    $frontendErr = Join-Path $devDir "frontend.err.log"
    $frontendProcess = Start-Process -FilePath $python -ArgumentList @("-m", "http.server", [string]$frontendPort, "--bind", $hostBind) -WorkingDirectory $root -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErr -PassThru -WindowStyle Hidden
    Set-Content -Path $frontendPid -Value $frontendProcess.Id

    if ($env:START_KITE_PROXY -eq "1") {
        Write-Host "Starting Kite quote proxy on :$kitePort ..."
        $kiteLog = Join-Path $devDir "kite.log"
        $kiteErr = Join-Path $devDir "kite.err.log"
        $kiteProcess = Start-Process -FilePath "npm" -ArgumentList @("start") -WorkingDirectory (Join-Path $root "server") -RedirectStandardOutput $kiteLog -RedirectStandardError $kiteErr -PassThru -WindowStyle Hidden
        Set-Content -Path $kitePid -Value $kiteProcess.Id
    }

    Start-Sleep -Seconds 2
    Invoke-EnsureLanAccess -Quiet
    Invoke-Status
    Write-Host ""
    Write-Host "Open in browser:"
    Write-Host "  http://localhost:$frontendPort/              Trading home"
    Write-Host "  http://localhost:$frontendPort/portfolio/    Portfolio"
    Write-Host "  http://localhost:$frontendPort/assistant/    Ask assistant"
    Write-Host "  http://localhost:$frontendPort/approvals/   Review live trades"
    Write-Host "  http://localhost:$frontendPort/compare/     Paper vs live A/B"
    Write-Host "  http://localhost:$frontendPort/screener/    Stock screener"
    Write-LanAccessHints
    Write-Host ""
    Write-Host "Logs: $devDir\*.log"
    Write-Host "Stop: .\scripts\dev.ps1 stop"
}

function Invoke-Stop {
    Write-Banner
    Remove-PidFile -PidFile $agentPid -Name "agent API"
    Remove-PidFile -PidFile $frontendPid -Name "frontend"
    Remove-PidFile -PidFile $kitePid -Name "Kite proxy"
    Stop-Port -Port $agentPort
    Stop-Port -Port $frontendPort
    if ($env:START_KITE_PROXY -eq "1") { Stop-Port -Port $kitePort }
    Write-Host "All dev services stopped."
}

function Invoke-Status {
    Write-Host ""
    Write-Host "Service status:"

    $agentRunning = $false
    if (Test-Path $agentPid) {
        $pidText = (Get-Content -Path $agentPid -TotalCount 1).Trim()
        if ($pidText -match "^\d+$") {
            $agentRunning = $null -ne (Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue)
        }
    }
    $frontendRunning = $false
    if (Test-Path $frontendPid) {
        $pidText = (Get-Content -Path $frontendPid -TotalCount 1).Trim()
        if ($pidText -match "^\d+$") {
            $frontendRunning = $null -ne (Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue)
        }
    }
    $kiteRunning = $false
    if (Test-Path $kitePid) {
        $pidText = (Get-Content -Path $kitePid -TotalCount 1).Trim()
        if ($pidText -match "^\d+$") {
            $kiteRunning = $null -ne (Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue)
        }
    }

    if ($agentRunning) { Write-Host "  [running] Agent API - http://localhost:$agentPort" } else { Write-Host "  [stopped] Agent API" }
    if ($frontendRunning) { Write-Host "  [running] Frontend - http://localhost:$frontendPort" } else { Write-Host "  [stopped] Frontend" }
    if ($kiteRunning) { Write-Host "  [running] Kite proxy - http://localhost:$kitePort" } else { Write-Host "  [stopped] Kite proxy" }

    try {
        $content = (Invoke-WebRequest -Uri "http://localhost:$agentPort/api/agent/health" -UseBasicParsing -TimeoutSec 5).Content
        if ($content) {
            Write-Host ""
            Write-Host "Agent health:"
            Write-Host $content
        }
    } catch {}
}

function Invoke-Paper {
    Write-Banner
    Write-Host "Running paper session and refreshing dashboard..."
    python scripts/generate_dashboard.py --refresh
    Write-Host "Done. View at http://localhost:$frontendPort/portfolio/"
}

function Invoke-Ab {
    Write-Banner
    Write-Host "Running paper vs live-shadow A/B comparison..."
    python scripts/run_ab_compare.py
    Write-Host "View at http://localhost:$frontendPort/compare/"
}

function Get-LanIPv4 {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notmatch "^127\." -and
            $_.IPAddress -notmatch "^169\.254\." -and
            $_.IPAddress -notmatch "^192\.168\.137\." -and
            $_.PrefixOrigin -in @("Dhcp", "Manual")
        }
}

function Get-PrimaryLanConfig {
    Get-NetIPConfiguration -ErrorAction SilentlyContinue |
        Where-Object { $_.NetAdapter.Status -eq "Up" -and $_.IPv4DefaultGateway } |
        Select-Object -First 1
}

function Test-IsAdmin {
    return ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-EnsureLanAccess {
    param([switch]$Quiet)
    $ports = @($frontendPort, $agentPort)
    foreach ($port in $ports) {
        $ruleName = "Bharat Scout TCP $port"
        $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        if (-not $existing) {
            try {
                New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow -Profile Any | Out-Null
                if (-not $Quiet) { Write-Host "Opened Windows Firewall (Private) for TCP $port" }
            } catch {
                if (-not $Quiet) {
                    Write-Host "Could not add firewall rule for TCP $port. Run as Administrator:"
                    Write-Host "  .\scripts\dev.ps1 lan"
                }
            }
        }
    }
    foreach ($svcName in @("fdPHost", "FDResPub")) {
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if (-not $svc) { continue }
        try {
            if ($svc.StartType -eq "Disabled") { Set-Service -Name $svcName -StartupType Manual -ErrorAction SilentlyContinue }
            if ($svc.Status -ne "Running") { Start-Service -Name $svcName -ErrorAction SilentlyContinue }
        } catch {}
    }
    $profile = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object { $_.IPv4Connectivity -eq "Internet" -or $_.IPv4Connectivity -eq "LocalNetwork" } | Select-Object -First 1
    if ($profile -and $profile.NetworkCategory -eq "Public") {
        try {
            Set-NetConnectionProfile -InterfaceIndex $profile.InterfaceIndex -NetworkCategory Private
            if (-not $Quiet) { Write-Host "Set network profile to Private so LAN devices can connect." }
        } catch {
            if (-not $Quiet) {
                Write-Host "Wi-Fi is Public. Set it to Private in Windows Settings, or run as Administrator: .\scripts\dev.ps1 lan"
            }
        }
    }
}

function Write-LanAccessHints {
    $hostName = $env:COMPUTERNAME.ToLowerInvariant()
    Write-Host ""
    Write-Host "Same Wi-Fi / LAN (bookmark this, it survives IP changes):"
    Write-Host "  http://${hostName}.local:$frontendPort/"
    Write-Host "  http://${hostName}:$frontendPort/"
    $ips = Get-LanIPv4
    if ($ips) {
        Write-Host "Current IP (can change with DHCP):"
        foreach ($addr in $ips) {
            Write-Host "  http://$($addr.IPAddress):$frontendPort/"
        }
    }
}

function Invoke-Lan {
    Write-Banner
    if (-not (Test-IsAdmin)) {
        Write-Host "Windows needs Administrator once to allow phones/laptops through the firewall."
        $ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        $script = Join-Path $PSScriptRoot "dev.ps1"
        try {
            Start-Process -FilePath $ps -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$script`" lan" -Wait
        } catch {
            Write-Host "UAC was declined. Right-click PowerShell -> Run as administrator, then:"
            Write-Host "  .\scripts\dev.ps1 lan"
        }
        Write-LanAccessHints
        Write-Host ""
        Write-Host "After allowing the firewall prompt, bookmark http://$($env:COMPUTERNAME.ToLowerInvariant()).local:$frontendPort/"
        return
    }
    Invoke-EnsureLanAccess
    Write-LanAccessHints
    Write-Host ""
    Write-Host "Use the .local URL on phones and other PCs. No domain purchase needed."
    Write-Host "If .local does not resolve, pin this PC's Wi-Fi IP:"
    Write-Host "  .\scripts\dev.ps1 pin-lan-ip"
}

function Invoke-PinLanIp {
    Write-Banner
    if (-not (Test-IsAdmin)) {
        Write-Host "Pinning the LAN IP needs Administrator PowerShell."
        Write-Host "Right-click PowerShell -> Run as administrator, then:"
        Write-Host "  cd $root"
        Write-Host "  .\scripts\dev.ps1 pin-lan-ip"
        return
    }
    $cfg = Get-PrimaryLanConfig
    if (-not $cfg) {
        Write-Host "No active Wi-Fi/Ethernet adapter with a gateway was found."
        return
    }
    $ipObj = $cfg.IPv4Address | Select-Object -First 1
    $ip = $ipObj.IPAddress
    $prefix = $ipObj.PrefixLength
    $gateway = $cfg.IPv4DefaultGateway.NextHop
    $dns = @($cfg.DNSServer.ServerAddresses | Where-Object { $_ -and $_ -notmatch ":" })
    if (-not $dns) { $dns = @($gateway) }
    $ifIndex = $cfg.InterfaceIndex
    $alias = $cfg.InterfaceAlias

    $existing = Get-NetIPAddress -InterfaceIndex $ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing -and $existing.PrefixOrigin -eq "Manual" -and $existing.IPAddress -eq $ip) {
        Write-Host "Already static: $ip on $alias"
        Write-LanAccessHints
        return
    }

    Write-Host "Pinning $alias to static $ip/$prefix gateway $gateway"
    Set-NetIPInterface -InterfaceIndex $ifIndex -Dhcp Disabled
    Get-NetIPAddress -InterfaceIndex $ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -ne $ip } |
        Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    $already = Get-NetIPAddress -InterfaceIndex $ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -eq $ip }
    if (-not $already) {
        New-NetIPAddress -InterfaceIndex $ifIndex -IPAddress $ip -PrefixLength $prefix -DefaultGateway $gateway | Out-Null
    } else {
        try {
            New-NetRoute -InterfaceIndex $ifIndex -DestinationPrefix "0.0.0.0/0" -NextHop $gateway -ErrorAction SilentlyContinue | Out-Null
        } catch {}
    }
    Set-DnsClientServerAddress -InterfaceIndex $ifIndex -ServerAddresses $dns
    Write-Host "Wi-Fi IP is now static. Bookmark: http://${ip}:$frontendPort/"
    Write-Host "Also bookmark: http://$($env:COMPUTERNAME.ToLowerInvariant()).local:$frontendPort/"
    Write-Host "Optional: in your router, reserve $ip for this PC so DHCP never gives it away."
}

function Get-StartupShortcutPath {
    return Join-Path ([Environment]::GetFolderPath("Startup")) "Bharat Scout Server.lnk"
}

function Install-StartupShortcut {
    $ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $script = Join-Path $PSScriptRoot "dev.ps1"
    $shortcutPath = Get-StartupShortcutPath
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $ps
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" start"
    $shortcut.WorkingDirectory = $root
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Start Bharat Scout agent API and frontend at Windows logon"
    $shortcut.Save()
    return $shortcutPath
}

function Invoke-InstallAutostart {
    Write-Banner
    $ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $script = Join-Path $PSScriptRoot "dev.ps1"
    $arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" start"
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    $action = New-ScheduledTaskAction -Execute $ps -Argument $arg -WorkingDirectory $root
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $logon.Delay = "PT30S"
    $triggers = @($logon)
    if ($isAdmin) {
        $startup = New-ScheduledTaskTrigger -AtStartup
        $startup.Delay = "PT1M"
        $triggers += $startup
    }
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

    $taskOk = $false
    try {
        Register-ScheduledTask `
            -TaskName $autostartTaskName `
            -Action $action `
            -Trigger $triggers `
            -Settings $settings `
            -Principal $principal `
            -Description "Starts Bharat Scout agent API (:8000) and frontend (:8080) when this PC boots or you log in." `
            -Force | Out-Null
        $taskOk = $true
    } catch {
        Write-Host "Scheduled task could not be created ($($_.Exception.Message.Trim()))."
        Write-Host "Falling back to a Startup-folder shortcut (runs when you log in)."
    }

    $shortcutPath = Install-StartupShortcut

    if ($taskOk) {
        Write-Host "Installed scheduled task: $autostartTaskName"
        if ($isAdmin) {
            Write-Host "  Triggers: at logon (+30s), at startup (+1m)"
        } else {
            Write-Host "  Triggers: at logon (+30s)"
            Write-Host "  Re-run this as Administrator to also start before you sign in."
        }
    }
    Write-Host "Installed Startup shortcut: $shortcutPath"
    Write-Host "  Action: .\scripts\dev.ps1 start"
    Write-Host ""
    Write-Host "Remove later with: .\scripts\dev.ps1 uninstall-autostart"
}

function Invoke-UninstallAutostart {
    Write-Banner
    $existing = Get-ScheduledTask -TaskName $autostartTaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $autostartTaskName -Confirm:$false
        Write-Host "Removed scheduled task: $autostartTaskName"
    } else {
        Write-Host "No autostart task named '$autostartTaskName' was found."
    }
    $shortcutPath = Get-StartupShortcutPath
    if (Test-Path $shortcutPath) {
        Remove-Item $shortcutPath -Force
        Write-Host "Removed Startup shortcut: $shortcutPath"
    } else {
        Write-Host "No Startup-folder shortcut was found."
    }
}

function Show-Usage {
    Write-Banner
    Write-Host ""
    Write-Host "Usage: .\scripts\dev.ps1 <command>"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  setup               Install deps, sync .env, run checks"
    Write-Host "  start               Start agent API + frontend"
    Write-Host "  stop                Stop all dev services"
    Write-Host "  status              Show what's running"
    Write-Host "  paper               Run paper trading session and refresh dashboard"
    Write-Host "  ab                  Run paper vs live-shadow A/B comparison"
    Write-Host "  install-autostart   Start the server when this PC boots / you log in"
    Write-Host "  uninstall-autostart Remove the boot autostart task"
    Write-Host "  lan                 Open firewall and print a stable same-Wi-Fi URL"
    Write-Host "  pin-lan-ip          Freeze the current Wi-Fi IP (Administrator)"
}

switch ($Command.ToLowerInvariant()) {
    "setup" { Invoke-Setup }
    "start" { Invoke-Start }
    "stop" { Invoke-Stop }
    "status" { Invoke-Status }
    "paper" { Invoke-Paper }
    "ab" { Invoke-Ab }
    "install-autostart" { Invoke-InstallAutostart }
    "uninstall-autostart" { Invoke-UninstallAutostart }
    "lan" { Invoke-Lan }
    "pin-lan-ip" { Invoke-PinLanIp }
    default { Show-Usage }
}