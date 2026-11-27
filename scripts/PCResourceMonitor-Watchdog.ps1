# PCResourceMonitor USB Watchdog
# Continuously checks iOS device USB connection, maintains backend (port 5001),
# iproxy.exe (port 2222 -> 22), and SSH reverse tunnel (port 5002 -> 5001).
# Spawns all child processes with CreateNoWindow = $true to ensure ZERO visible console pop-ups.

$ErrorActionPreference = "Continue"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

# Ports configuration (configurable via environment variables)
$backendPort = if ($env:PC_MONITOR_PORT) { [int]$env:PC_MONITOR_PORT } else { 5001 }
$tunnelPort = if ($env:PC_MONITOR_TUNNEL_PORT) { [int]$env:PC_MONITOR_TUNNEL_PORT } else { 5002 }
$iproxyPort = if ($env:PC_MONITOR_IPROXY_PORT) { [int]$env:PC_MONITOR_IPROXY_PORT } else { 2222 }
$devicePort = if ($env:PC_MONITOR_DEVICE_PORT) { [int]$env:PC_MONITOR_DEVICE_PORT } else { 22 }

# Python executable resolution (virtual environment or system PATH)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $pythonExe)) {
    $pythonCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue }
    if ($pythonCmd) { $pythonExe = $pythonCmd.Source }
}

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$watchdogLog = Join-Path $logDir "watchdog.log"
$backendOutLog = Join-Path $logDir "backend.out.log"
$backendErrLog = Join-Path $logDir "backend.err.log"
$iproxyOutLog = Join-Path $logDir "iproxy-$iproxyPort.out.log"
$iproxyErrLog = Join-Path $logDir "iproxy-$iproxyPort.err.log"
$tunnelOutLog = Join-Path $logDir "tunnel-$tunnelPort.out.log"
$tunnelErrLog = Join-Path $logDir "tunnel-$tunnelPort.err.log"

# Tool and utility path resolution
$ideviceIdExe = if ($env:IDEVICE_ID_PATH) { $env:IDEVICE_ID_PATH } else { Join-Path $projectRoot "tools\idevice_id.exe" }
if (-not (Test-Path $ideviceIdExe)) {
    $cmd = Get-Command idevice_id.exe -ErrorAction SilentlyContinue
    if ($cmd) { $ideviceIdExe = $cmd.Source }
}

$iproxyExe = if ($env:IPROXY_PATH) { $env:IPROXY_PATH } else { Join-Path $projectRoot "tools\iproxy.exe" }
if (-not (Test-Path $iproxyExe)) {
    $cmd = Get-Command iproxy.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iproxyExe = $cmd.Source }
}

$sshExe = if ($env:SSH_PATH) { $env:SSH_PATH } else { "C:\Windows\System32\OpenSSH\ssh.exe" }
if (-not (Test-Path $sshExe)) {
    $cmd = Get-Command ssh.exe -ErrorAction SilentlyContinue
    if ($cmd) { $sshExe = $cmd.Source }
}

$keyPath = if ($env:SSH_KEY_PATH) { $env:SSH_KEY_PATH } else { Join-Path $env:USERPROFILE ".ssh\id_rsa" }

function Write-WatchdogLog([string]$message) {
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$timestamp] $message"
    try {
        if ((Test-Path $watchdogLog) -and (Get-Item $watchdogLog).Length -gt 1MB) {
            Get-Content $watchdogLog -Tail 1000 | Set-Content $watchdogLog
        }
        Add-Content -Path $watchdogLog -Value $line
    } catch {}
}

function Test-TcpPort([string]$hostAddress, [int]$port, [int]$timeoutMs = 400) {
    $tcp = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $tcp.BeginConnect($hostAddress, $port, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne($timeoutMs, $false)
        if ($wait -and $tcp.Connected) {
            $tcp.EndConnect($async)
            $tcp.Close()
            return $true
        }
    } catch {}
    finally {
        $tcp.Dispose()
    }
    return $false
}

function Start-SilentProcess {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string]$Arguments = "",
        [string]$WorkingDirectory = $projectRoot,
        [string]$StdOutPath = $null,
        [string]$StdErrPath = $null
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $false
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    if ($WorkingDirectory) {
        $psi.WorkingDirectory = $WorkingDirectory
    }

    if ($StdOutPath -or $StdErrPath) {
        $cmdLine = "`"$FilePath`""
        if ($Arguments) {
            $cmdLine += " $Arguments"
        }
        if ($StdOutPath) {
            $cmdLine += " > `"$StdOutPath`""
        }
        if ($StdErrPath) {
            $cmdLine += " 2> `"$StdErrPath`""
        }
        $psi.FileName = "$env:ComSpec"
        $psi.Arguments = "/c `"$cmdLine`""
    } else {
        $psi.FileName = $FilePath
        $psi.Arguments = $Arguments
    }

    [System.Diagnostics.Process]::Start($psi) | Out-Null
}

function Get-ConnectedDeviceUdid {
    if (-not (Test-Path $ideviceIdExe)) {
        return $null
    }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $ideviceIdExe
        $psi.Arguments = "-l"
        $psi.CreateNoWindow = $true
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

        $proc = [System.Diagnostics.Process]::Start($psi)
        $output = $proc.StandardOutput.ReadToEnd()
        $proc.WaitForExit(1500) | Out-Null
        if ($output) {
            foreach ($line in ($output -split "`r?`n")) {
                $trimmed = $line.Trim()
                if ($trimmed.Length -ge 24) {
                    return $trimmed
                }
            }
        }
    } catch {}
    return $null
}

function Stop-PCResourceMonitorTunnels {
    try {
        $sshProcs = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$tunnelPort:127.0.0.1:$backendPort*" }
        foreach ($p in $sshProcs) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }

        $iproxyProcs = Get-CimInstance Win32_Process -Filter "Name = 'iproxy.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$iproxyPort*$devicePort*" }
        foreach ($p in $iproxyProcs) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function Ensure-BackendRunning {
    $isBackendUp = Test-TcpPort "127.0.0.1" $backendPort 500
    if (-not $isBackendUp) {
        Write-WatchdogLog "Backend port $backendPort not responding. Starting Waitress backend with pythonw.exe..."
        Start-SilentProcess -FilePath $pythonExe -Arguments "-m backend.run" `
            -WorkingDirectory $projectRoot -StdOutPath $backendOutLog -StdErrPath $backendErrLog
        Start-Sleep -Milliseconds 800
    }
}

function Ensure-IproxyRunning {
    $isIproxyListening = Test-TcpPort "127.0.0.1" $iproxyPort 400
    $iproxyProcs = Get-CimInstance Win32_Process -Filter "Name = 'iproxy.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$iproxyPort*$devicePort*" }

    if ((-not $isIproxyListening) -or (-not $iproxyProcs) -or ($iproxyProcs.Count -gt 1)) {
        Write-WatchdogLog "Restarting iproxy $iproxyPort $devicePort (listening=$isIproxyListening, procCount=$($iproxyProcs.Count))..."
        foreach ($p in $iproxyProcs) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Start-SilentProcess -FilePath $iproxyExe -Arguments "$iproxyPort $devicePort" `
            -WorkingDirectory $projectRoot -StdOutPath $iproxyOutLog -StdErrPath $iproxyErrLog
        Start-Sleep -Milliseconds 400
        return $true
    }
    return $false
}

function Ensure-SshTunnelRunning([bool]$forceRestart = $false) {
    $sshProcs = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$tunnelPort:127.0.0.1:$backendPort*" }

    if ($forceRestart -or (-not $sshProcs) -or ($sshProcs.Count -gt 1)) {
        Write-WatchdogLog "Starting SSH reverse tunnel $tunnelPort:127.0.0.1:$backendPort..."
        foreach ($p in $sshProcs) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }

        $sshArgs = "-i `"`"$keyPath`"`" -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ExitOnForwardFailure=yes -o ServerAliveInterval=2 -o ServerAliveCountMax=1 -o ConnectTimeout=3 -o TCPKeepAlive=yes -N -R $tunnelPort:127.0.0.1:$backendPort -p $iproxyPort root@127.0.0.1"

        Start-SilentProcess -FilePath $sshExe -Arguments $sshArgs `
            -WorkingDirectory $projectRoot -StdOutPath $tunnelOutLog -StdErrPath $tunnelErrLog
        Start-Sleep -Milliseconds 400
    }
}

Write-WatchdogLog "PCResourceMonitor USB Watchdog started (zero-window mode)."
$lastDeviceState = $false

while ($true) {
    try {
        # 1. Ensure backend is always running
        Ensure-BackendRunning

        # 2. Check iOS USB connection
        $udid = Get-ConnectedDeviceUdid
        $isDeviceConnected = [bool]$udid

        if ($isDeviceConnected) {
            if (-not $lastDeviceState) {
                Write-WatchdogLog "iOS device connected over USB (UDID: $udid)"
                $lastDeviceState = $true
            }

            # 3. Maintain iproxy
            $iproxyRestarted = Ensure-IproxyRunning

            # 4. Maintain SSH reverse tunnel (force restart if iproxy was just restarted)
            Ensure-SshTunnelRunning -forceRestart $iproxyRestarted
        } else {
            if ($lastDeviceState) {
                Write-WatchdogLog "iOS device disconnected from USB. Cleaning up port $iproxyPort/$tunnelPort tunnels..."
                Stop-PCResourceMonitorTunnels
                $lastDeviceState = $false
            }
        }
    } catch {
        Write-WatchdogLog "Watchdog loop error: $_"
    }

    Start-Sleep -Seconds 1
}
