# Cleanly stops PCResourceMonitor Watchdog, Backend, iproxy, and SSH tunnel.

$ErrorActionPreference = "Continue"

$backendPort = if ($env:PC_MONITOR_PORT) { [int]$env:PC_MONITOR_PORT } else { 5001 }
$tunnelPort = if ($env:PC_MONITOR_TUNNEL_PORT) { [int]$env:PC_MONITOR_TUNNEL_PORT } else { 5002 }
$iproxyPort = if ($env:PC_MONITOR_IPROXY_PORT) { [int]$env:PC_MONITOR_IPROXY_PORT } else { 2222 }
$devicePort = if ($env:PC_MONITOR_DEVICE_PORT) { [int]$env:PC_MONITOR_DEVICE_PORT } else { 22 }

Write-Host "Stopping PCResourceMonitor processes..."

# 1. Stop Watchdog process
$watchdogProcs = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'pwsh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*PCResourceMonitor-Watchdog.ps1*" }
foreach ($p in $watchdogProcs) {
    Write-Host "Stopping Watchdog PID $($p.ProcessId)..."
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# 2. Stop SSH reverse tunnel
$sshProcs = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$tunnelPort:127.0.0.1:$backendPort*" }
foreach ($p in $sshProcs) {
    Write-Host "Stopping SSH tunnel PID $($p.ProcessId)..."
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# 3. Stop iproxy
$iproxyProcs = Get-CimInstance Win32_Process -Filter "Name = 'iproxy.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$iproxyPort*$devicePort*" }
foreach ($p in $iproxyProcs) {
    Write-Host "Stopping iproxy PID $($p.ProcessId)..."
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# 4. Stop backend server
$backendProcs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*backend.run*" }
foreach ($p in $backendProcs) {
    Write-Host "Stopping Backend PID $($p.ProcessId)..."
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "PCResourceMonitor stopped cleanly."
