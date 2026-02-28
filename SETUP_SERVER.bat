@echo off
setlocal enabledelayedexpansion
title iMon Server Setup

:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

echo ==========================================
echo      iMon Server Installation Setup
echo ==========================================

set "PYTHON_CMD="

REM --- CHECK 1: Try to force finding the NEW Python 3.11 first ---
if exist "%ProgramFiles%\Python311\python.exe" (
    "%ProgramFiles%\Python311\python.exe" -m pip --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD="%ProgramFiles%\Python311\python.exe""
        goto :install_deps
    )
)

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    "%LocalAppData%\Programs\Python\Python311\python.exe" -m pip --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD="%LocalAppData%\Programs\Python\Python311\python.exe""
        goto :install_deps
    )
)

REM --- CHECK 2: py -3.11 command ---
py -3.11 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3.11"
    goto :install_deps
)

REM --- CHECK 3: python command (only if it has pip) ---
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python -m pip --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python"
        goto :install_deps
    )
)

REM --- IF NO WORKING PYTHON FOUND, INSTALL IT ---
echo.
echo [!] No working Python found.
echo [*] Checking for winget...

winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Installing Python 3.11 via Winget...
    winget install -e --id Python.Python.3.11 --scope machine --accept-package-agreements --accept-source-agreements
) else (
    echo [!] Winget not found. Using PowerShell fallback...
    echo [*] Downloading Python 3.11 installer...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python_installer.exe'"
    
    if not exist python_installer.exe (
        echo [ERROR] Download failed.
        echo Please download Python manually from https://www.python.org/downloads/
        pause
        exit /b
    )
    
    echo [*] Installing Python 3.11 silently...
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del python_installer.exe
)

REM --- VERIFY INSTALLATION ---
echo [*] Verifying installation...
timeout /t 3 >nul

REM Force check specific paths again
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PYTHON_CMD="%ProgramFiles%\Python311\python.exe""
    goto :install_deps
)

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD="%LocalAppData%\Programs\Python\Python311\python.exe""
    goto :install_deps
)

REM Fallback to py -3.11
py -3.11 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3.11"
    goto :install_deps
)

echo.
echo [WARN] Python installed but not detected in current session.
echo [INFO] Please RESTART your computer and run this script again.
pause
exit /b

:install_deps
echo.
echo [*] Using Python: %PYTHON_CMD%
echo [*] Installing dependencies...
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r server/requirements.txt
%PYTHON_CMD% -m pip install -r client/requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies.
    echo [INFO] This might be because of the broken C:\Python314 installation.
    echo [INFO] Try uninstalling "Python 3.14" from Control Panel if possible.
    pause
    exit /b
)

REM --- RUN CONFIGURATION ---
echo.
echo [*] Starting Configuration...
call %PYTHON_CMD% configure_deployment.py

echo.
echo ==========================================
echo      SETUP COMPLETE
echo ==========================================
pause
