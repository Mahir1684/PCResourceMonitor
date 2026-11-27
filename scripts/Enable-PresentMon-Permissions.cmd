@echo off
echo ========================================================
echo Adding %USERNAME% to 'Performance Log Users' group...
echo This enables real-time PresentMon ETW frame rate tracing
echo without requiring admin privileges on every run.
echo ========================================================
net localgroup "Performance Log Users" %USERNAME% /add
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] User %USERNAME% successfully added to Performance Log Users!
    echo NOTE: Please sign out of Windows and sign back in for the new group token to take effect.
) else (
    echo.
    echo [ERROR] Failed to add user. Please right-click this script and select 'Run as administrator'.
)
pause
