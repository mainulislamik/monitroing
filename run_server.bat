@echo off
setlocal
cd /d %~dp0

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "server\app.py"
) else (
  python "server\app.py"
)

endlocal
