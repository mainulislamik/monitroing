@echo off
setlocal EnableDelayedExpansion
title iMon Client Installer (Python)

:: Check for Administrator privileges
set "ADMIN_MODE=1"
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    net session >nul 2>&1
    if %errorlevel% neq 0 (
        echo [WARN] Administrator permission not granted. Continuing in user mode.
        set "ADMIN_MODE=0"
    )
)

echo ========================================================
echo       iMon Client Installer (Python Environment)
echo ========================================================
echo.

:: Define Installation Paths
if "%ADMIN_MODE%"=="1" (
    set "INSTALL_DIR=%ProgramData%\iMon"
    set "STARTUP_DIR=%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup"
    set "RUN_REG_PATH=HKLM\Software\Microsoft\Windows\CurrentVersion\Run"
) else (
    set "INSTALL_DIR=%APPDATA%\iMon"
    set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    set "RUN_REG_PATH=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
)
set "CLIENT_SCRIPT=client.py"
set "CLIENT_EXE=SystemUpdate.exe"
set "SOURCE_SCRIPT=%~dp0%CLIENT_SCRIPT%"
set "TARGET_SCRIPT=%INSTALL_DIR%\%CLIENT_SCRIPT%"
set "SOURCE_EXE=%~dp0%CLIENT_EXE%"
set "TARGET_EXE=%INSTALL_DIR%\%CLIENT_EXE%"
set "CONFIG_DIR=%APPDATA%\iMon"
set "CONFIG_FILE=%CONFIG_DIR%\config.json"
set "DRIVER_INF=%~dp0drivers\vb-cable\VBCAudio.inf"
set "REQ_FILE=%~dp0requirements.txt"
set "PYTHON_EXE="
set "PYTHONW_EXE="
set "LAUNCHER_BAT=%INSTALL_DIR%\start_client.bat"
set "ACTIVE_SCRIPT=%SOURCE_SCRIPT%"
set "USE_EXE=0"

if not exist "%SOURCE_SCRIPT%" if not exist "%SOURCE_EXE%" (
    echo [ERROR] Could not find %CLIENT_SCRIPT% or %CLIENT_EXE% in current directory.
    echo Please make sure this batch file is in the same folder as client files.
    pause
    exit /b 1
)

:: Create Install Directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: 1. Ask for Server IP
echo Enter Server IP/Host (example: 192.168.1.10 or myserver)
set /p SERVER_INPUT=Server IP/Host: 
if "%SERVER_INPUT%"=="" (
    echo No input provided. Exiting.
    pause
    exit /b 1
)

:: Normalize Server URL
echo %SERVER_INPUT% | findstr /r /c:"://" >nul
if not errorlevel 1 (
    set "SERVER_URL=%SERVER_INPUT%"
) else (
    echo %SERVER_INPUT% | findstr ":" >nul
    if not errorlevel 1 (
        set "SERVER_URL=http://%SERVER_INPUT%"
    ) else (
        set "SERVER_URL=http://%SERVER_INPUT%:5000"
    )
)

:: 2. Stop Existing Instances
echo [INFO] Stopping existing client instances...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*client.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
taskkill /IM "SystemUpdate.exe" /F >nul 2>&1
taskkill /IM "pythonw.exe" /F >nul 2>&1
if exist "%SOURCE_EXE%" (
    set "USE_EXE=1"
)

if "%USE_EXE%"=="1" goto exe_mode

:: Resolve Python path
call :resolve_python
if not defined PYTHON_EXE (
    echo [WARN] Python not found. Downloading and installing Python...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
    if not exist "%TEMP%\python_installer.exe" (
        echo [ERROR] Failed to download Python installer.
        pause
        exit /b 1
    )
    echo [INFO] Installing Python (this may take a minute)...
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir="C:\Program Files\Python311"
    call :resolve_python
)

if not defined PYTHON_EXE (
    echo [ERROR] Python installation failed. Please install Python manually.
    pause
    exit /b 1
)

echo [OK] Using Python: %PYTHON_EXE%
echo [OK] Using Pythonw: %PYTHONW_EXE%

echo [INFO] Checking connection to %SERVER_URL% ...
"%PYTHON_EXE%" -c "import socket,urllib.parse; u=urllib.parse.urlparse(r'%SERVER_URL%'); h=u.hostname; p=u.port or (443 if u.scheme=='https' else 80); s=socket.create_connection((h,p),5); s.close()"
if !errorlevel! neq 0 (
    echo [ERROR] Cannot connect to %SERVER_URL%.
    echo [ERROR] Use the SERVER machine IP, not localhost, unless server is on same PC.
    pause
    exit /b 1
)
echo [OK] Server is reachable.

:: 4. Install Dependencies
echo [INFO] Installing required libraries...
if exist "%REQ_FILE%" (
    "%PYTHON_EXE%" -m pip install --upgrade pip
    "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
) else (
    echo [WARN] requirements.txt not found. Attempting manual install...
    "%PYTHON_EXE%" -m pip install python-socketio[client] websocket-client mss Pillow dxcam numpy soundcard pywin32 sounddevice
)

if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies for %PYTHON_EXE%.
    pause
    exit /b 1
)

:: 5. Save Configuration
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1
> "%CONFIG_FILE%" echo {"server_url":"%SERVER_URL%"}
echo [OK] Configuration saved: %SERVER_URL%

:: 6. Copy Source Files to Permanent Location
copy /Y "%SOURCE_SCRIPT%" "%TARGET_SCRIPT%" >nul
if exist "%TARGET_SCRIPT%" (
    echo [OK] Client script installed to: %TARGET_SCRIPT%
    set "ACTIVE_SCRIPT=%SOURCE_SCRIPT%"
) else (
    echo [ERROR] Failed to copy client script.
    pause
    exit /b 1
)

:: Verify runtime imports
echo [INFO] Verifying runtime imports...
"%PYTHON_EXE%" -c "import socketio,mss,PIL,numpy,sounddevice,websocket" >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Runtime verification failed. Client cannot start.
    pause
    exit /b 1
)

:: Create launcher bat using absolute pythonw path
> "%LAUNCHER_BAT%" echo @echo off
>> "%LAUNCHER_BAT%" echo cd /d "%INSTALL_DIR%"
>> "%LAUNCHER_BAT%" echo "%PYTHONW_EXE%" "%ACTIVE_SCRIPT%" --server "%SERVER_URL%"
goto setup_autostart

:exe_mode
echo [OK] Using executable mode: %CLIENT_EXE%
powershell -NoProfile -Command "$u=[uri]'%SERVER_URL%'; $p=if($u.Port -gt 0){$u.Port}else{80}; $c=New-Object System.Net.Sockets.TcpClient; try { $iar=$c.BeginConnect($u.Host,$p,$null,$null); if(-not $iar.AsyncWaitHandle.WaitOne(5000,$false)){exit 1}; $c.EndConnect($iar); exit 0 } catch { exit 1 } finally { $c.Close() }" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot connect to %SERVER_URL%.
    echo [ERROR] Use the SERVER machine IP, not localhost, unless server is on same PC.
    pause
    exit /b 1
)
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1
> "%CONFIG_FILE%" echo {"server_url":"%SERVER_URL%"}
copy /Y "%SOURCE_EXE%" "%TARGET_EXE%" >nul
if not exist "%TARGET_EXE%" (
    echo [ERROR] Failed to copy %CLIENT_EXE%.
    pause
    exit /b 1
)
> "%LAUNCHER_BAT%" echo @echo off
>> "%LAUNCHER_BAT%" echo cd /d "%INSTALL_DIR%"
>> "%LAUNCHER_BAT%" echo "%TARGET_EXE%" --server "%SERVER_URL%"

:: 7. Create Startup Shortcut
:setup_autostart
if not exist "%STARTUP_DIR%" mkdir "%STARTUP_DIR%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP_DIR%\iMonClient.lnk'); $s.TargetPath = '%LAUNCHER_BAT%'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Save()"
echo [OK] Startup shortcut created.

:: 8. Add to Registry Run
reg add "%RUN_REG_PATH%" /v "iMonClient" /t REG_SZ /d "\"%LAUNCHER_BAT%\"" /f >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Registry auto-start enabled.
) else (
    echo [WARN] Could not set registry auto-start. Startup shortcut is still configured.
)

:: 9. Create Desktop Shortcut
echo [INFO] Creating Desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\iMon Client.lnk'); $s.TargetPath = '%LAUNCHER_BAT%'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Save()"
echo [OK] Desktop shortcut created.

:: 10. Install Loopback Driver (if present)
if "%ADMIN_MODE%"=="1" if exist "%DRIVER_INF%" (
    echo [INFO] Found loopback driver. Installing...
    pnputil /add-driver "%DRIVER_INF%" /install >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Loopback driver installed successfully.
    ) else (
        echo [WARN] Loopback driver installation might have failed or is already installed.
    )
)
if "%ADMIN_MODE%"=="0" (
    echo [WARN] Driver installation skipped (admin permission not granted).
)

echo.
echo ========================================================
echo       Installation Complete!
echo ========================================================
echo The client will now start in the background.
echo.

:: Start the client
start "" "%LAUNCHER_BAT%"
set "CLIENT_STARTED=0"
for /L %%A in (1,1,8) do (
    timeout /t 1 >nul
    powershell -Command "$found = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*client.py*' -or $_.Name -eq 'SystemUpdate.exe' }; if($found){exit 0}else{exit 1}" >nul 2>&1
    if !errorlevel! equ 0 (
        set "CLIENT_STARTED=1"
        goto :started_ok
    )
)
:started_ok
if "%CLIENT_STARTED%"=="0" (
    echo [ERROR] Client process did not stay running.
    echo [INFO] Running client in this window for diagnosis...
    if "%USE_EXE%"=="1" (
        "%TARGET_EXE%" --server "%SERVER_URL%"
    ) else (
        "%PYTHON_EXE%" "%ACTIVE_SCRIPT%" --server "%SERVER_URL%"
    )
    pause
    exit /b 1
)
echo [OK] Client started successfully.

pause
exit /b 0

:resolve_python
set "PYTHON_EXE="
set "PYTHONW_EXE="
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
    set "PYTHONW_EXE=%ProgramFiles%\Python311\pythonw.exe"
    goto :eof
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    set "PYTHONW_EXE=%LocalAppData%\Programs\Python\Python311\pythonw.exe"
    goto :eof
)
py -3.11 -c "import sys; print(sys.executable)" > "%TEMP%\imon_py_path.txt" 2>nul
if not errorlevel 1 (
    set /p PYTHON_EXE=<"%TEMP%\imon_py_path.txt"
)
if not defined PYTHON_EXE (
    py -3 -c "import sys; print(sys.executable)" > "%TEMP%\imon_py_path.txt" 2>nul
    if not errorlevel 1 (
        set /p PYTHON_EXE=<"%TEMP%\imon_py_path.txt"
    )
)
if not defined PYTHON_EXE (
    python -c "import sys; print(sys.executable)" > "%TEMP%\imon_py_path.txt" 2>nul
    if not errorlevel 1 (
        set /p PYTHON_EXE=<"%TEMP%\imon_py_path.txt"
    )
)
if defined PYTHON_EXE (
    for %%I in ("%PYTHON_EXE%") do set "PYTHONW_EXE=%%~dpIpythonw.exe"
    if not exist "!PYTHONW_EXE!" set "PYTHONW_EXE=%PYTHON_EXE%"
)
if exist "%TEMP%\imon_py_path.txt" del /q "%TEMP%\imon_py_path.txt" >nul 2>&1
goto :eof
