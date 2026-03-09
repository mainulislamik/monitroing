@echo off
setlocal
set "APPDATA_DIR=%APPDATA%\iMon"
set "CONFIG_FILE=%APPDATA_DIR%\config.json"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "CLIENT_SCRIPT=%~dp0client.py"
set "PY_CMD="
echo Enter Server IP/Host (example: 192.168.1.10 or myserver)
set /p SERVER_INPUT=Server IP/Host: 
if "%SERVER_INPUT%"=="" (
  echo No input provided. Exiting.
  exit /b 1
)
set "SERVER_URL="
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
if not exist "%APPDATA_DIR%" mkdir "%APPDATA_DIR%"
> "%CONFIG_FILE%" echo {"server_url":"%SERVER_URL%"}
echo Saved: %SERVER_URL%

if exist "%LocalAppData%\Programs\Python\Python311\pythonw.exe" (
  set "PY_CMD=%LocalAppData%\Programs\Python\Python311\pythonw.exe"
) else if exist "%ProgramFiles%\Python311\pythonw.exe" (
  set "PY_CMD=%ProgramFiles%\Python311\pythonw.exe"
) else (
  set "PY_CMD=pythonw.exe"
)

set "EXE_PATH="
if exist "%~dp0dist\\SystemUpdate.exe" (
  set "EXE_PATH=%~dp0dist\\SystemUpdate.exe"
) else if exist "%~dp0SystemUpdate.exe" (
  set "EXE_PATH=%~dp0SystemUpdate.exe"
)
if not exist "%STARTUP_DIR%" (
  mkdir "%STARTUP_DIR%" >nul 2>&1
)
if not "%EXE_PATH%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell=New-Object -ComObject WScript.Shell; $sc=$shell.CreateShortcut('%STARTUP_DIR%\\SystemUpdate.lnk'); $sc.TargetPath='%EXE_PATH%'; $sc.WorkingDirectory='%~dp0'; $sc.Save()"
  if exist "%STARTUP_DIR%\\SystemUpdate.lnk" (
    echo Startup shortcut created: %STARTUP_DIR%\SystemUpdate.lnk
  ) else (
    echo Shortcut failed; copying executable to Startup...
    copy /Y "%EXE_PATH%" "%STARTUP_DIR%\SystemUpdate.exe" >nul
  )
) else if exist "%CLIENT_SCRIPT%" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell=New-Object -ComObject WScript.Shell; $sc=$shell.CreateShortcut('%STARTUP_DIR%\\iMonClient.lnk'); $sc.TargetPath='%PY_CMD%'; $sc.Arguments='\"%CLIENT_SCRIPT%\"'; $sc.WorkingDirectory='%~dp0'; $sc.Save()"
  if exist "%STARTUP_DIR%\\iMonClient.lnk" (
    echo Startup shortcut created: %STARTUP_DIR%\iMonClient.lnk
  ) else (
    echo Failed to create startup shortcut for client.py.
  )
) else (
  echo Could not locate SystemUpdate.exe or client.py next to this script.
)
if exist "%~dp0dist\\SystemUpdate.exe" (
  start "" "%~dp0dist\\SystemUpdate.exe"
) else if exist "%~dp0SystemUpdate.exe" (
  start "" "%~dp0SystemUpdate.exe"
) else if exist "%CLIENT_SCRIPT%" (
  start "" "%PY_CMD%" "%CLIENT_SCRIPT%"
) else (
  echo No runnable client file found.
)
endlocal
