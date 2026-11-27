$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Locate iproxy executable (environment variable, local tools folder, or PATH)
$iproxyExe = if ($env:IPROXY_PATH) { $env:IPROXY_PATH } else { Join-Path $projectRoot "tools\iproxy.exe" }
if (-not (Test-Path $iproxyExe)) {
    $cmd = Get-Command iproxy.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iproxyExe = $cmd.Source }
}

$localPort = if ($env:PC_MONITOR_IPROXY_PORT) { [int]$env:PC_MONITOR_IPROXY_PORT } else { 2222 }
$devicePort = if ($env:PC_MONITOR_DEVICE_PORT) { [int]$env:PC_MONITOR_DEVICE_PORT } else { 22 }

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$existing = Get-CimInstance Win32_Process -Filter "Name = 'iproxy.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$localPort*$devicePort*" }
if (-not $existing) {
    $stdoutLog = Join-Path $logDir "iproxy-$localPort.out.log"
    $stderrLog = Join-Path $logDir "iproxy-$localPort.err.log"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "$env:ComSpec"
    $psi.Arguments = "/c `"`"$iproxyExe`" $localPort $devicePort > `"$stdoutLog`" 2> `"$stderrLog`"`""
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $false
    [System.Diagnostics.Process]::Start($psi) | Out-Null
}
