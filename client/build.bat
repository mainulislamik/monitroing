@echo off
setlocal
set "CLIENT_DIST=%~dp0dist"
set "ROOT_DIST=%~dp0..\dist"
set "ROOT_DIR=%~dp0.."
set "PYTHON_CMD="

if not exist "%CLIENT_DIST%" mkdir "%CLIENT_DIST%"
if not exist "%ROOT_DIST%" mkdir "%ROOT_DIST%"

if exist "%ProgramFiles%\Python311\python.exe" (
    set "PYTHON_CMD=%ProgramFiles%\Python311\python.exe"
) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
) else (
    set "PYTHON_CMD=python"
)

"%PYTHON_CMD%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    exit /b 1
)

"%PYTHON_CMD%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    exit /b 1
)

"%PYTHON_CMD%" -m PyInstaller --noconsole --onefile --hidden-import=engineio.async_drivers.threading --hidden-import=websocket --name "SystemUpdate" "%~dp0client.py"
if errorlevel 1 (
    echo [ERROR] Failed to build SystemUpdate.exe.
    exit /b 1
)

copy /Y "%~dp0client.py" "%CLIENT_DIST%\client.py" >nul
copy /Y "%~dp0requirements.txt" "%CLIENT_DIST%\requirements.txt" >nul
copy /Y "%~dp0SetServerIP.bat" "%CLIENT_DIST%\SetServerIP.bat" >nul
if exist "%~dp0dist\SystemUpdate.exe" copy /Y "%~dp0dist\SystemUpdate.exe" "%CLIENT_DIST%\SystemUpdate.exe" >nul

if exist "%ROOT_DIST%\InstallClient.bat" copy /Y "%ROOT_DIST%\InstallClient.bat" "%CLIENT_DIST%\InstallClient.bat" >nul
if exist "%ROOT_DIST%\UNINSTALL_CLIENT.bat" copy /Y "%ROOT_DIST%\UNINSTALL_CLIENT.bat" "%CLIENT_DIST%\UNINSTALL_CLIENT.bat" >nul
if exist "%ROOT_DIST%\README_INSTALL.txt" copy /Y "%ROOT_DIST%\README_INSTALL.txt" "%CLIENT_DIST%\README_INSTALL.txt" >nul

copy /Y "%CLIENT_DIST%\client.py" "%ROOT_DIST%\client.py" >nul
copy /Y "%CLIENT_DIST%\requirements.txt" "%ROOT_DIST%\requirements.txt" >nul
copy /Y "%CLIENT_DIST%\SetServerIP.bat" "%ROOT_DIST%\SetServerIP.bat" >nul
if exist "%CLIENT_DIST%\SystemUpdate.exe" copy /Y "%CLIENT_DIST%\SystemUpdate.exe" "%ROOT_DIST%\SystemUpdate.exe" >nul
if exist "%CLIENT_DIST%\InstallClient.bat" copy /Y "%CLIENT_DIST%\InstallClient.bat" "%ROOT_DIST%\InstallClient.bat" >nul
if exist "%CLIENT_DIST%\UNINSTALL_CLIENT.bat" copy /Y "%CLIENT_DIST%\UNINSTALL_CLIENT.bat" "%ROOT_DIST%\UNINSTALL_CLIENT.bat" >nul
if exist "%CLIENT_DIST%\README_INSTALL.txt" copy /Y "%CLIENT_DIST%\README_INSTALL.txt" "%ROOT_DIST%\README_INSTALL.txt" >nul

if exist "%CLIENT_DIST%\SystemDrive.exe" del /q "%CLIENT_DIST%\SystemDrive.exe"
if exist "%ROOT_DIST%\SystemDrive.exe" del /q "%ROOT_DIST%\SystemDrive.exe"

if not exist "%ROOT_DIST%\drivers" mkdir "%ROOT_DIST%\drivers"
xcopy "%ROOT_DIR%\server\drivers\*" "%ROOT_DIST%\drivers\" /E /I /Y >nul

echo.
echo Build complete! Client package is ready at:
echo %ROOT_DIST%
endlocal
