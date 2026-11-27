' Silent background launcher for PCResourceMonitor-Watchdog.ps1
' Starts the USB auto-reconnect watchdog with zero visible console windows.

Set objFSO = CreateObject("Scripting.FileSystemObject")
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
ps1Path = objFSO.BuildPath(scriptDir, "PCResourceMonitor-Watchdog.ps1")

Set objShell = CreateObject("WScript.Shell")
strCommand = "powershell.exe -NonInteractive -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1Path & """"
objShell.Run strCommand, 0, False
