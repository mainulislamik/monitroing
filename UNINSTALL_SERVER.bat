@echo off
setlocal

:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

echo ========================================================
echo          iMon Server Uninstaller
echo ========================================================
echo.

set "INSTALL_DIR=%~dp0"
set "TEMP_SCRIPT=%TEMP%\imon_server_cleanup.bat"

echo [*] Preparing uninstaller...
(
echo @echo off
echo timeout /t 2 /nobreak ^>nul
echo echo [*] Stopping Server Processes...
echo taskkill /F /IM python.exe /T ^>nul 2^>^&1
echo echo [*] Removing files...
echo rmdir /s /q "%INSTALL_DIR%"
echo if exist "%INSTALL_DIR%" (
echo     echo [WARNING] Some files could not be deleted. Please delete "%INSTALL_DIR%" manually.
echo ^) else (
echo     echo [SUCCESS] Server uninstalled and files removed.
echo ^)
echo echo.
echo echo Press any key to exit...
echo pause ^>nul
echo del "%TEMP_SCRIPT%"
) > "%TEMP_SCRIPT%"

echo [*] Starting cleanup process...
start "" "%TEMP_SCRIPT%"

exit
