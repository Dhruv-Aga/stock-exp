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

    Write-Host "Starting agent API on :$agentPort ..."
    $env:HOST_BIND = $hostBind
    $env:AGENT_API_PORT = [string]$agentPort
    $agentLog = Join-Path $devDir "agent.log"
    $agentErr = Join-Path $devDir "agent.err.log"
    $agentProcess = Start-Process -FilePath "python" -ArgumentList @("run_agent_api.py") -WorkingDirectory $root -RedirectStandardOutput $agentLog -RedirectStandardError $agentErr -PassThru -WindowStyle Hidden
    Set-Content -Path $agentPid -Value $agentProcess.Id

    Write-Host "Starting frontend on ${hostBind}:$frontendPort ..."
    $env:FRONTEND_PORT = [string]$frontendPort
    $frontendLog = Join-Path $devDir "frontend.log"
    $frontendErr = Join-Path $devDir "frontend.err.log"
    $frontendProcess = Start-Process -FilePath "python" -ArgumentList @("-m", "http.server", [string]$frontendPort, "--bind", $hostBind) -WorkingDirectory $root -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErr -PassThru -WindowStyle Hidden
    Set-Content -Path $frontendPid -Value $frontendProcess.Id

    if ($env:START_KITE_PROXY -eq "1") {
        Write-Host "Starting Kite quote proxy on :$kitePort ..."
        $kiteLog = Join-Path $devDir "kite.log"
        $kiteErr = Join-Path $devDir "kite.err.log"
        $kiteProcess = Start-Process -FilePath "npm" -ArgumentList @("start") -WorkingDirectory (Join-Path $root "server") -RedirectStandardOutput $kiteLog -RedirectStandardError $kiteErr -PassThru -WindowStyle Hidden
        Set-Content -Path $kitePid -Value $kiteProcess.Id
    }

    Start-Sleep -Seconds 2
    Invoke-Status
    Write-Host ""
    Write-Host "Open in browser:"
    Write-Host "  http://localhost:$frontendPort/              Trading home"
    Write-Host "  http://localhost:$frontendPort/portfolio/    Portfolio"
    Write-Host "  http://localhost:$frontendPort/assistant/    Ask assistant"
    Write-Host "  http://localhost:$frontendPort/approvals/   Review live trades"
    Write-Host "  http://localhost:$frontendPort/compare/     Paper vs live A/B"
    Write-Host "  http://localhost:$frontendPort/screener/    Stock screener"
    if ($hostBind -eq "0.0.0.0") {
        $lanIps = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch "^127\." } | Select-Object -ExpandProperty IPAddress)
        if ($lanIps) {
            foreach ($ip in $lanIps) {
                Write-Host "  http://${ip}:$frontendPort/                   Home network"
            }
        }
    }
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

function Show-Usage {
    Write-Banner
    Write-Host ""
    Write-Host "Usage: .\scripts\dev.ps1 <command>"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  setup     Install deps, sync .env, run checks"
    Write-Host "  start     Start agent API + frontend"
    Write-Host "  stop      Stop all dev services"
    Write-Host "  status    Show what's running"
    Write-Host "  paper     Run paper trading session and refresh dashboard"
    Write-Host "  ab        Run paper vs live-shadow A/B comparison"
}

switch ($Command.ToLowerInvariant()) {
    "setup" { Invoke-Setup }
    "start" { Invoke-Start }
    "stop" { Invoke-Stop }
    "status" { Invoke-Status }
    "paper" { Invoke-Paper }
    "ab" { Invoke-Ab }
    default { Show-Usage }
}