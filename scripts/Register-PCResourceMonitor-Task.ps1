# Registers or unregisters a Windows Scheduled Task for PCResourceMonitor Watchdog.
# Automatically starts the watchdog silently in the background at user logon.

param(
    [switch]$Unregister
)

$taskName = "PCResourceMonitor-Watchdog"

if ($Unregister) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Unregistered Scheduled Task: $taskName"
    } else {
        Write-Host "Scheduled Task $taskName does not exist."
    }
    return
}

$vbsPath = Join-Path $PSScriptRoot "Start-PCResourceMonitor-Watchdog.vbs"
if (-not (Test-Path $vbsPath)) {
    Write-Error "Launcher script not found: $vbsPath"
    return
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Successfully registered Scheduled Task: $taskName (Runs at user logon silently)"
