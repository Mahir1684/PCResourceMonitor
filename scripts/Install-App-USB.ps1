# Installs/updates PCResourceMonitor on the iOS device over USB tunnel (default port 2222)
# Usage: .\scripts\Install-App-USB.ps1

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Locate IPA (prefer dist/, fallback to native build directory)
$ipaPath = Join-Path $projectRoot "dist\PCResourceMonitor.ipa"
if (-not (Test-Path $ipaPath)) {
    $ipaPath = Join-Path $projectRoot "native\.theos\obj\debug\PCResourceMonitor.ipa"
}
if (-not (Test-Path $ipaPath)) {
    Write-Error "IPA file not found at $ipaPath. Build with Theos or place prebuilt IPA in dist/."
    exit 1
}

$port = if ($env:PC_MONITOR_IPROXY_PORT) { [int]$env:PC_MONITOR_IPROXY_PORT } else { 2222 }
$keyPath = if ($env:SSH_KEY_PATH) { $env:SSH_KEY_PATH } else { Join-Path $env:USERPROFILE ".ssh\id_rsa" }

$scpExe = if ($env:SCP_PATH) { $env:SCP_PATH } else { "C:\Windows\System32\OpenSSH\scp.exe" }
if (-not (Test-Path $scpExe)) {
    $cmd = Get-Command scp.exe -ErrorAction SilentlyContinue
    if ($cmd) { $scpExe = $cmd.Source }
}

$sshExe = if ($env:SSH_PATH) { $env:SSH_PATH } else { "C:\Windows\System32\OpenSSH\ssh.exe" }
if (-not (Test-Path $sshExe)) {
    $cmd = Get-Command ssh.exe -ErrorAction SilentlyContinue
    if ($cmd) { $sshExe = $cmd.Source }
}

Write-Host "Copying PCResourceMonitor.ipa to iOS device over USB (port $port)..."
& $scpExe -i "$keyPath" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedKeyTypes=+ssh-rsa" -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=NUL" -P $port "$ipaPath" "root@127.0.0.1:/tmp/PCResourceMonitor.ipa"

Write-Host "Installing IPA via appinst on iOS device..."
& $sshExe -i "$keyPath" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedKeyTypes=+ssh-rsa" -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=NUL" -p $port root@127.0.0.1 "/usr/bin/appinst /tmp/PCResourceMonitor.ipa && /usr/bin/uiopen pcmonitor://"

Write-Host "PCResourceMonitor installed and launched successfully on iOS device!"
