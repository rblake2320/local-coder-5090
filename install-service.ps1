#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Install Local Coder 5090 as a Windows service using NSSM.

.DESCRIPTION
  Registers the local_coder_browser.py HTTP server as a Windows service
  so it starts automatically with the machine.

  Prerequisites:
    - NSSM at D:\tools\nssm\nssm.exe  (download: nssm.cc)
    - Python 3.12 at C:\Python312\python.exe
    - Ollama installed and running

.EXAMPLE
  # Install (run in Admin PowerShell):
  .\install-service.ps1

  # Or specify custom install dir:
  .\install-service.ps1 -InstallDir "D:\local-coder"

  # Remove the service:
  .\install-service.ps1 -Uninstall
#>

param(
    [string]$InstallDir    = "C:\Users\techai\local-coder",
    [string]$ServiceName   = "LocalCoder",
    [string]$NssmExe       = "D:\tools\nssm\nssm.exe",
    [string]$PythonExe     = "C:\Python312\python.exe",
    [string]$RepoDir       = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [switch]$Uninstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-Prereqs {
    if (-not (Test-Path $NssmExe)) {
        Write-Error "NSSM not found at $NssmExe.`nDownload from https://nssm.cc and extract to D:\tools\nssm\"
    }
    if (-not (Test-Path $PythonExe)) {
        Write-Error "Python not found at $PythonExe."
    }
}

function Uninstall-Service {
    Write-Host "Stopping and removing service '$ServiceName'..." -ForegroundColor Yellow
    & $NssmExe stop $ServiceName 2>$null
    Start-Sleep 2
    & $NssmExe remove $ServiceName confirm
    Write-Host "Service '$ServiceName' removed." -ForegroundColor Green
}

function Install-Service {
    # Create workspace dirs
    $workspace = Join-Path $InstallDir "workspace"
    $logsDir   = Join-Path $InstallDir "logs"
    New-Item -ItemType Directory -Force -Path $workspace | Out-Null
    New-Item -ItemType Directory -Force -Path $logsDir   | Out-Null

    # Copy repo files to install dir if different
    if ($RepoDir -ne $InstallDir) {
        Write-Host "Copying repo files to $InstallDir..." -ForegroundColor Cyan
        Copy-Item -Path "$RepoDir\*" -Destination $InstallDir -Recurse -Force
    }

    $scriptPath = Join-Path $InstallDir "scripts\local_coder_browser.py"
    if (-not (Test-Path $scriptPath)) {
        Write-Error "Server script not found at $scriptPath."
    }

    # Stop existing service if present
    $existing = & $NssmExe status $ServiceName 2>&1
    if ($existing -notmatch "No such service") {
        Write-Host "Stopping existing service..." -ForegroundColor Yellow
        & $NssmExe stop $ServiceName 2>$null
        Start-Sleep 2
        & $NssmExe remove $ServiceName confirm 2>$null
    }

    Write-Host "Installing service '$ServiceName'..." -ForegroundColor Cyan

    # Register
    & $NssmExe install $ServiceName $PythonExe "$scriptPath --no-open"

    # Configure
    & $NssmExe set $ServiceName AppDirectory $InstallDir
    & $NssmExe set $ServiceName AppStdout (Join-Path $logsDir "local_coder_stdout.log")
    & $NssmExe set $ServiceName AppStderr (Join-Path $logsDir "local_coder_stderr.log")
    & $NssmExe set $ServiceName AppRotateFiles 1
    & $NssmExe set $ServiceName AppRotateBytes 10485760       # 10 MB
    & $NssmExe set $ServiceName Start SERVICE_AUTO_START
    & $NssmExe set $ServiceName AppRestartDelay 3000

    # Environment variables
    & $NssmExe set $ServiceName AppEnvironmentExtra `
        "LOCAL_CODER_HOME=$InstallDir" `
        "LOCAL_CODER_WORKSPACE=$workspace" `
        "LOCAL_CODER_MODEL_BASE=http://localhost:11434" `
        "LOCAL_CODER_MODEL=qwen3:32b" `
        "LOCAL_CODER_FAST_MODEL=gemma4:latest"

    # Start it
    Write-Host "Starting service..." -ForegroundColor Cyan
    & $NssmExe start $ServiceName

    Start-Sleep 3
    $status = & $NssmExe status $ServiceName
    Write-Host "Service status: $status" -ForegroundColor ($status -eq "SERVICE_RUNNING" ? "Green" : "Yellow")

    Write-Host ""
    Write-Host "Local Coder 5090 installed as Windows service '$ServiceName'." -ForegroundColor Green
    Write-Host "  UI:      http://127.0.0.1:8022/"
    Write-Host "  Status:  http://127.0.0.1:8022/status"
    Write-Host "  Logs:    $logsDir"
    Write-Host ""
    Write-Host "To manage:"
    Write-Host "  $NssmExe start|stop|restart $ServiceName"
    Write-Host "  python ops\daily_control_win.py status"
}

# ── entry point ───────────────────────────────────────────────────────────────
Test-Prereqs
if ($Uninstall) { Uninstall-Service } else { Install-Service }
