import time
import base64
import socketio
try:
    import dxcam
except Exception:
    dxcam = None
from PIL import Image
import io
import sys
import os
import ctypes
import socket
import datetime
import mss
import json
try:
    import tkinter as tk
    from tkinter import simpledialog
except Exception:
    tk = None
    simpledialog = None

# --- CONFIGURATION ---
# Server URL - update this if the server is on another machine
SERVER_URL = None
LOG_FILE = r"C:\Users\Public\imon_debug.log"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "iMon")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_mouse_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def get_screen_size():
    # SM_CXSCREEN = 0, SM_CYSCREEN = 1
    width = ctypes.windll.user32.GetSystemMetrics(0)
    height = ctypes.windll.user32.GetSystemMetrics(1)
    return width, height

def log(msg):
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] {msg}"
        print(formatted_msg)
        with open(LOG_FILE, "a") as f:
            f.write(formatted_msg + "\n")
    except:
        pass

def load_server_url():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        url = (data or {}).get("server_url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    except Exception:
        return None
    return None

def save_server_url(url):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"server_url": url}, f)
        return True
    except Exception as e:
        log(f"Failed to save server URL: {e}")
        return False

def normalize_server_input(value):
    value = (value or "").strip()
    if not value:
        return None
    if "://" in value:
        return value
    if value.startswith("//"):
        return "http:" + value
    if ":" in value:
        return "http://" + value
    return f"http://{value}:5000"

def prompt_server_url():
    if tk is None or simpledialog is None:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    entered = simpledialog.askstring("iMon", "Enter Server IP / Host (example: 192.168.1.10)")
    root.destroy()
    return normalize_server_input(entered)

sio = socketio.Client()
try:
    employee_name = socket.gethostname()
except:
    employee_name = 'Employee-' + str(os.getpid())

@sio.event
def connect():
    log(f'Connected to server: {SERVER_URL}')
    sio.emit('register_employee', {'name': employee_name})

@sio.event
def disconnect():
    log('Disconnected from server')

@sio.event
def connect_error(data):
    log(f'Connect error: {data}')

def create_dxcam_camera():
    if dxcam is None:
        return None
    try:
        return dxcam.create(output_color="RGB")
    except Exception as e:
        log(f"dxcam create failed: {e}")
        return None

def main():
    global SERVER_URL
    log("Client started")

    server_override = None
    if "--server" in sys.argv:
        try:
            idx = sys.argv.index("--server")
            server_override = sys.argv[idx + 1]
        except Exception:
            server_override = None
    if "--set-server" in sys.argv:
        SERVER_URL = prompt_server_url()
        if not SERVER_URL:
            log("Server URL not set. Exiting.")
            return
        save_server_url(SERVER_URL)
    else:
        SERVER_URL = normalize_server_input(server_override) or load_server_url() or prompt_server_url()
        if not SERVER_URL:
            log("Server URL not set. Exiting.")
            return
        save_server_url(SERVER_URL)
    
    # Set Process Priority to Low (IDLE) using ctypes (No external dependency)
    try:
        pid = os.getpid()
        # 0x00000040 is IDLE_PRIORITY_CLASS
        handle = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0200, False, pid) # QUERY_INFO | SET_INFO
        if handle:
            ctypes.windll.kernel32.SetPriorityClass(handle, 0x00000040)
            ctypes.windll.kernel32.CloseHandle(handle)
            log("Priority set to IDLE")
    except Exception as e:
        log(f"Failed to set priority: {e}")

    camera = create_dxcam_camera()
    sct = mss.mss()
    
    # Wait for server connection
    first_capture = True
    while True:
        try:
            if not sio.connected:
                log(f"Attempting to connect to {SERVER_URL}...")
                sio.connect(
                    SERVER_URL,
                    transports=["websocket", "polling"],
                    wait_timeout=15,
                )
            
            screen_width, screen_height = get_screen_size()
            consecutive_empty_frames = 0
            
            while sio.connected:
                # 1. Capture Screen
                frame = None
                if camera:
                    try:
                        frame = camera.grab()
                    except TypeError:
                        frame = camera.grab()
                    except Exception as e:
                        log(f"dxcam grab error: {e}")
                        frame = None
                
                img = None
                capture_method = "dxcam"
                
                if frame is not None:
                    # DXCam returned a frame (screen changed)
                    consecutive_empty_frames = 0
                    img = Image.fromarray(frame)
                elif camera is not None:
                    # DXCam active but returned None (static screen)
                    # Do NOT fallback to MSS here, just skip image update
                    consecutive_empty_frames += 1
                    # Only re-init if idle for a VERY long time (e.g. ~5 minutes = 2500 frames)
                    # to prevent flicker
                    if consecutive_empty_frames >= 2500:
                        log("Long idle detected; refreshing camera")
                        camera = create_dxcam_camera()
                        consecutive_empty_frames = 0
                else:
                    # No DXCam available, use MSS
                    capture_method = "mss"
                    monitors = sct.monitors
                    if not monitors:
                        log("No monitors found by mss")
                        sio.sleep(1.0)
                        continue
                        
                    monitor = monitors[1] if len(monitors) > 1 else monitors[0]
                    try:
                        sct_img = sct.grab(monitor)
                        img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                    except Exception as e:
                        log(f"mss grab failed: {e}")
                        sio.sleep(1.0)
                        continue

                if first_capture and img:
                    log(f"First screen capture successful using {capture_method}")
                    first_capture = False

                # 2. Process & Send Image (if any)
                if img is not None:
                    img.thumbnail((1280, 720))
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=55)
                    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    sio.emit('screen_share', {'image': img_str})
                
                # 3. Mouse Tracking (ALWAYS send, even if screen is static)
                mx, my = get_mouse_pos()
                px = mx / screen_width if screen_width else 0
                py = my / screen_height if screen_height else 0
                sio.emit('mouse_move', {'x': px, 'y': py})
                
                sio.sleep(0.12)
                
        except Exception as e:
            log(f"Main loop error: {e}")
            time.sleep(5)  # Wait before retry

if __name__ == '__main__':
    main()
