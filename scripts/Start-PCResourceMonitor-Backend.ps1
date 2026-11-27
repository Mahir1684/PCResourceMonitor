$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

# Resolve Python executable (virtual environment or PATH fallback)
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
$stdoutLog = Join-Path $logDir "backend.out.log"
$stderrLog = Join-Path $logDir "backend.err.log"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "$env:ComSpec"
$psi.Arguments = "/c `"`"$pythonExe`" -m backend.run > `"$stdoutLog`" 2> `"$stderrLog`"`""
$psi.CreateNoWindow = $true
$psi.UseShellExecute = $false
$psi.WorkingDirectory = $projectRoot
[System.Diagnostics.Process]::Start($psi) | Out-Null
