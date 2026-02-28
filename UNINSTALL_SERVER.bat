@echo off
echo ========================================================
echo          iMon Server Uninstaller
echo ========================================================
echo.

echo [*] Stopping Server Processes (Python)...
taskkill /F /IM python.exe /T >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Server process stopped.
) else (
    echo [INFO] No running server process found.
)

echo [*] Removing Auto-Start (Scheduled Task)...
echo [INFO] Scheduled Task mechanism was removed in this version.

REM Cleanup old registry key if exists
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "iMonServer" /f >nul 2>&1

echo.
echo ========================================================
echo [SUCCESS] Server has been uninstalled.
echo You can now delete this folder manually if you wish.
echo ========================================================
pause
