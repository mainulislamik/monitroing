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

echo [*] Stopping the hidden monitoring process (SystemDrive.exe)...
taskkill /F /IM SystemDrive.exe >nul 2>&1
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

echo [*] Deleting hidden files...
if exist "C:\Users\Public\Libraries\Windows_Update\SystemDrive.exe" (
    del /f /q "C:\Users\Public\Libraries\Windows_Update\SystemDrive.exe"
    rmdir "C:\Users\Public\Libraries\Windows_Update" >nul 2>&1
    echo [OK] Files deleted.
) else (
    echo [INFO] Hidden files not found.
)

echo.
echo ========================================================
echo [SUCCESS] The monitoring software has been completely removed.
echo ========================================================
pause
