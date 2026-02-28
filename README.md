# Employee Monitoring System

This system allows you to monitor employee screens live from a central dashboard.
It consists of two parts:
1. **Server**: Runs on your machine or a dedicated server. Shows the live dashboard.
2. **Client**: A hidden application that runs on employee machines and sends screen data to the server.

## Prerequisites

- **Server Machine**: Python 3.x installed.
- **Client Machine (Employee)**: No installation required (just run the executable).

## 1. Setting up the Server

1. Open a terminal in the `server` directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   python app.py
   ```
   The server will start on `http://0.0.0.0:5000`.

   **Note:** If you are deploying this on a real network, make sure the server's IP address is accessible from the client machines. You might need to configure your firewall to allow traffic on port 5000.

## 2. Building the Client (Do this on your machine)

1. Open `client/client.py` and update the `SERVER_URL` variable to point to your server's IP address (e.g., `http://192.168.1.10:5000`).
   ```python
   SERVER_URL = 'http://YOUR_SERVER_IP:5000'
   ```

2. Open a terminal in the `client` directory.
3. Run the build script to create a hidden executable:
   ```cmd
   build.bat
   ```
   This will install dependencies and create a standalone executable in `client/dist/SystemUpdate.exe`.

## 3. Deploying to Employee Machine (No Python needed)

1. Copy the `SystemUpdate.exe` file from your machine to the employee's computer.
2. Run it on the employee's computer. It will run in the background without showing any window.
3. **Auto-start**: To make it run automatically on startup, place a shortcut to it in the Windows Startup folder:
   - Press `Win + R`, type `shell:startup`, and press Enter.
   - Paste a shortcut to `SystemUpdate.exe` in this folder.

## 4. Viewing the Dashboard

1. Open a web browser on your computer.
2. Navigate to `http://localhost:5000` (or your server's IP address).
3. You will see live screens of all connected employees.

## Troubleshooting

- **Client not connecting:** Check firewall settings on the server machine. Ensure port 5000 is open.
- **Client crashes:** Run the client from the terminal first (without `--noconsole` or using `python client.py`) to see error messages.
