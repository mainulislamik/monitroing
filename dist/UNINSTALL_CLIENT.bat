@echo off
:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

echo ========================================================
echo       iMon Client Uninstaller (Hidden Remover)
echo ========================================================
echo.

echo [*] Stopping the monitoring process...
taskkill /F /IM SystemDrive.exe >nul 2>&1
taskkill /F /IM SystemUpdate.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Process stopped.
) else (
    echo [INFO] Process was not running.
)

echo [*] Removing Auto-Start Registry Key (All Users)...
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v "WindowsSystemDrive" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Auto-Start disabled (HKLM).
) else (
    echo [INFO] HKLM key not found.
)

REM Cleanup old user-specific key if exists
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "SystemDrive" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "WindowsSystemDrive" /f >nul 2>&1

echo [*] Removing Startup folder shortcut and copies...
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
del /f /q "%STARTUP_DIR%\SystemUpdate.lnk" >nul 2>&1
del /f /q "%STARTUP_DIR%\SystemUpdate.exe" >nul 2>&1

echo [*] Deleting hidden files...
if exist "C:\Users\Public\Libraries\Windows_Update\SystemDrive.exe" (
    del /f /q "C:\Users\Public\Libraries\Windows_Update\SystemDrive.exe"
    rmdir "C:\Users\Public\Libraries\Windows_Update" >nul 2>&1
    echo [OK] Files deleted.
) else (
    echo [INFO] Hidden files not found.
)

echo [*] Removing configuration files...
set "APPDATA_DIR=%APPDATA%\iMon"
if exist "%APPDATA_DIR%\config.json" del /f /q "%APPDATA_DIR%\config.json" >nul 2>&1
if exist "%APPDATA_DIR%" rmdir /q "%APPDATA_DIR%" >nul 2>&1

echo.
echo ========================================================
echo [SUCCESS] The monitoring software has been completely removed.
echo ========================================================
pause
