@echo off
setlocal enabledelayedexpansion
title Update Client IP and Rebuild

:: Check for Python
set "PYTHON_CMD="
if exist "%ProgramFiles%\Python311\python.exe" set "PYTHON_CMD="%ProgramFiles%\Python311\python.exe""
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_CMD="%LocalAppData%\Programs\Python\Python311\python.exe""
if not defined PYTHON_CMD py -3.11 --version >nul 2>&1 && set "PYTHON_CMD=py -3.11"
if not defined PYTHON_CMD python --version >nul 2>&1 && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo [ERROR] Python not found! Please run SETUP_SERVER.bat first.
    pause
    exit /b
)

echo [*] Using Python: %PYTHON_CMD%

echo.
echo [*] Detecting Server IP and updating client code...
%PYTHON_CMD% update_ip.py

echo.
echo [*] Rebuilding Client Executable...
%PYTHON_CMD% -m PyInstaller --noconsole --onefile --hidden-import=engineio.async_drivers.threading --hidden-import=websocket --name=SystemDrive client/client.py

echo.
echo [*] Moving to dist_package...
if not exist "dist_package" mkdir "dist_package"
move /Y "dist\SystemDrive.exe" "dist_package\SystemDrive.exe"

echo.
echo ========================================================
echo [SUCCESS] Client Rebuilt with Correct IP Address!
echo ========================================================
echo.
echo Please do the following on the EMPLOYEE PC:
echo 1. Run UNINSTALL_CLIENT.bat (if already installed)
echo 2. Copy the NEW 'dist_package' folder to the employee PC.
echo 3. Run INSTALL_CLIENT.bat (Run as Administrator)
echo.
pause
