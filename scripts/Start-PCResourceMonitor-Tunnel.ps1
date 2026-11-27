$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Resolve SSH executable and private key path
$sshExe = if ($env:SSH_PATH) { $env:SSH_PATH } else { "C:\Windows\System32\OpenSSH\ssh.exe" }
if (-not (Test-Path $sshExe)) {
    $cmd = Get-Command ssh.exe -ErrorAction SilentlyContinue
    if ($cmd) { $sshExe = $cmd.Source }
}

$keyPath = if ($env:SSH_KEY_PATH) { $env:SSH_KEY_PATH } else { Join-Path $env:USERPROFILE ".ssh\id_rsa" }
$backendPort = if ($env:PC_MONITOR_PORT) { [int]$env:PC_MONITOR_PORT } else { 5001 }
$tunnelPort = if ($env:PC_MONITOR_TUNNEL_PORT) { [int]$env:PC_MONITOR_TUNNEL_PORT } else { 5002 }
$iproxyPort = if ($env:PC_MONITOR_IPROXY_PORT) { [int]$env:PC_MONITOR_IPROXY_PORT } else { 2222 }

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$existing = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$tunnelPort:127.0.0.1:$backendPort*" }
if (-not $existing) {
    $stdoutLog = Join-Path $logDir "tunnel-$tunnelPort.out.log"
    $stderrLog = Join-Path $logDir "tunnel-$tunnelPort.err.log"
    $sshArgs = "-i `"`"$keyPath`"`" -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ExitOnForwardFailure=yes -o ServerAliveInterval=2 -o ServerAliveCountMax=1 -o ConnectTimeout=3 -o TCPKeepAlive=yes -N -R $tunnelPort:127.0.0.1:$backendPort -p $iproxyPort root@127.0.0.1"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "$env:ComSpec"
    $psi.Arguments = "/c `"`"$sshExe`" $sshArgs > `"$stdoutLog`" 2> `"$stderrLog`"`""
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $false
    [System.Diagnostics.Process]::Start($psi) | Out-Null
}
