import time
import base64
import socketio
import urllib.request
import subprocess
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
import threading
import numpy as np
import zipfile
import tempfile
import shutil
import glob
try:
    import soundcard as sc
except Exception:
    sc = None
try:
    import comtypes
except Exception:
    comtypes = None
try:
    import pythoncom
except Exception:
    pythoncom = None
try:
    import sounddevice as sd
except Exception:
    sd = None
try:
    import tkinter as tk
    from tkinter import simpledialog
except Exception:
    tk = None
    simpledialog = None
was_just_updated = False

# --- CONFIGURATION ---
# Server URL - update this if the server is on another machine
SERVER_URL = None
LOG_FILE = r"C:\Users\Public\imon_debug.log"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "iMon")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STREAM_MAX_WIDTH = 2560
STREAM_MAX_HEIGHT = 1440
JPEG_QUALITY = 90

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
    print(msg)
    try:
        with open("client.log", "a") as f:
            f.write(f"{datetime.datetime.now()} - {msg}\n")
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

def get_unique_machine_name():
    try:
        hostname = socket.gethostname()
        if not hostname:
            hostname = os.environ.get('COMPUTERNAME')
        if not hostname:
            hostname = os.environ.get('USERNAME')
        
        # Check for invalid names (case-insensitive)
        invalid_names = ['unknown', 'localhost', '']
        if not hostname or str(hostname).lower() in invalid_names:
             # If still unknown, use a random ID to ensure uniqueness
             import uuid
             hostname = f"Client-{str(uuid.uuid4())[:8]}"
             
        return hostname
    except:
        import uuid
        return f"Client-{str(uuid.uuid4())[:8]}"

employee_name = get_unique_machine_name()

@sio.event
def connect():
    log(f'Connected to server: {SERVER_URL}')
    sio.emit('register_employee', {'name': employee_name})
    global was_just_updated
    if was_just_updated:
        try:
            sio.emit('update_complete', {'name': employee_name, 'ts': datetime.datetime.now().isoformat()})
        finally:
            was_just_updated = False

@sio.event
def disconnect():
    log('Disconnected from server')

@sio.event
def connect_error(data):
    log(f'Connect error: {data}')

@sio.event
def perform_update(data):
    log("Received update command from server.")
    update_client()

@sio.event
def request_frame(data=None):
    try:
        sct = mss.mss()
        monitors = sct.monitors
        if not monitors:
            return
        monitor = monitors[1] if len(monitors) > 1 else monitors[0]
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        img.thumbnail((STREAM_MAX_WIDTH, STREAM_MAX_HEIGHT))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        sio.emit('screen_share', {'image': img_str})
    except Exception as e:
        log(f"Immediate frame error: {e}")
def update_client():
    try:
        is_frozen = getattr(sys, 'frozen', False)
        filename = "SystemUpdate.exe" if is_frozen else "client.py"
        download_url = f"{SERVER_URL}/download/client/{filename}"
        log(f"Downloading update from {download_url}...")
        target_file = os.path.abspath(sys.executable) if is_frozen else os.path.abspath(__file__)
        install_dir = os.path.dirname(target_file)
        new_filename = os.path.join(install_dir, f"{os.path.basename(target_file)}.new")
        try:
            urllib.request.urlretrieve(download_url, new_filename)
        except Exception as e:
            log(f"Download failed: {e}")
            try:
                sio.emit('update_failed', {'name': employee_name, 'error': str(e)})
            except:
                pass
            return
        log("Download complete. Preparing to restart...")
        current_pid = os.getpid()
        if is_frozen:
            start_cmd = f'"{target_file}" --updated'
        else:
            python_exe = sys.executable
            py_dir = os.path.dirname(python_exe)
            pythonw = os.path.join(py_dir, "pythonw.exe")
            if os.path.exists(pythonw):
                start_cmd = f'"{pythonw}" "{target_file}" --updated'
            else:
                start_cmd = f'"{python_exe}" "{target_file}" --updated >nul 2>&1'
        bat_script = f"""@echo off
timeout /t 2 /nobreak >nul
taskkill /F /PID {current_pid}
move /Y "{new_filename}" "{target_file}"
start "" {start_cmd}
del "%~f0"
"""
        bat_path = os.path.join(install_dir, "update_client.bat")
        with open(bat_path, "w") as f:
            f.write(bat_script)
        try:
            sio.emit('update_start', {'name': employee_name})
        except:
            pass
        subprocess.Popen(bat_path, shell=True, cwd=install_dir)
        sys.exit(0)
        
    except Exception as e:
        log(f"Update failed: {e}")

def get_loopback_recorder(sr):
    if sc is None:
        log("soundcard library not available")
        return None
    
    candidates = []
    
    # 1. Try default speaker loopback (Highest Priority)
    try:
        spk = sc.default_speaker()
        mic = sc.get_microphone(spk.name, include_loopback=True)
        if mic:
            candidates.append(mic)
    except Exception as e:
        log(f"Default speaker check failed: {e}")

    # 2. Try all speakers loopback
    try:
        for s in sc.all_speakers():
            try:
                mic = sc.get_microphone(s.name, include_loopback=True)
                if mic and mic.name not in [c.name for c in candidates]:
                    candidates.append(mic)
            except:
                continue
    except Exception as e:
        log(f"Scanning speakers failed: {e}")

    # 3. Try direct microphone capture for known virtual devices
    target_names = ["Cable Output", "Stereo Mix", "What U Hear", "Wave Out Mix"]
    try:
        for m in sc.all_microphones(include_loopback=True):
            for target in target_names:
                if target.lower() in m.name.lower():
                    if m.name not in [c.name for c in candidates]:
                        candidates.append(m)
    except Exception as e:
        log(f"Scanning microphones failed: {e}")

    if not candidates:
        return None

    # Test candidates for active audio signal
    log(f"Testing {len(candidates)} devices for audio signal...")
    best_candidate = candidates[0] # Default fallback
    
    for mic in candidates:
        try:
            # Short test recording
            with mic.recorder(samplerate=sr) as test_rec:
                data = test_rec.record(numframes=int(sr * 0.1)) # 100ms
                peak = np.max(np.abs(data))
                if peak > 0.005: # Sound detected
                    log(f"Active audio found on: {mic.name} (Peak: {peak:.4f})")
                    return mic.recorder(samplerate=sr)
        except Exception as e:
            log(f"Test failed for {mic.name}: {e}")
            continue
            
    log(f"No active audio found. Defaulting to: {best_candidate.name}")
    return best_candidate.recorder(samplerate=sr)

def create_dxcam_camera():
    if dxcam is None:
        return None
    try:
        return dxcam.create(output_color="RGB")
    except Exception as e:
        log(f"dxcam create failed: {e}")
        return None

sio_event_lock = threading.Lock()

@sio.event
def enable_loopback(data=None):
    if sc is None:
        try:
            sio.emit('loopback_unavailable', {'name': employee_name})
        except:
            pass
        return
    def start_loopback():
        try:
            sr = 48000
            rec = get_loopback_recorder(sr)
            if rec is None:
                try:
                    sio.emit('loopback_unavailable', {'name': employee_name})
                except:
                    pass
                return
            try:
                sio.emit('loopback_enabled', {'name': employee_name})
            except:
                pass
            with rec:
                while sio.connected:
                    data = rec.record(numframes=1024)
                    if data is None:
                        continue
                    if data.ndim == 1:
                        data = np.stack([data, data], axis=1)
                    clipped = np.clip(data, -1.0, 1.0)
                    interleaved = (clipped * 32767.0).astype(np.int16).flatten()
                    payload = base64.b64encode(interleaved.tobytes()).decode('utf-8')
                    with sio_event_lock:
                        sio.emit('audio_chunk', {'source': 'system', 'sr': sr, 'ch': 2, 'pcm': payload})
        except Exception as e:
            log(f"Enable loopback error: {e}")
            try:
                sio.emit('loopback_unavailable', {'name': employee_name, 'error': str(e)})
            except:
                pass
    threading.Thread(target=start_loopback, daemon=True).start()

@sio.event
def install_loopback(data=None):
    try:
        sid_name = employee_name
        try:
            sio.emit('loopback_install_status', {'name': sid_name, 'status': 'starting'})
        except:
            pass
        sr = 48000
        rec = get_loopback_recorder(sr)
        if rec is not None:
            try:
                sio.emit('loopback_enabled', {'name': sid_name})
            except:
                pass
            return
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        candidates = [
            os.path.join(base_dir, 'drivers', 'vb-cable', 'VBCAudio.inf'),
            os.path.join(base_dir, 'dist', 'drivers', 'vb-cable', 'VBCAudio.inf'),
        ]
        inf_path = None
        for p in candidates:
            if os.path.exists(p):
                inf_path = p
                break
        # Try server-provided zip bundle first
        extracted_dir = None
        if inf_path is None and SERVER_URL:
            try:
                zip_url = SERVER_URL.rstrip('/') + '/drivers/vb-cable.zip'
                tmp_zip = os.path.join(base_dir, 'vb-cable.zip')
                urllib.request.urlretrieve(zip_url, tmp_zip)
                if os.path.exists(tmp_zip):
                    extracted_dir = tempfile.mkdtemp(prefix="vb_cable_")
                    with zipfile.ZipFile(tmp_zip, 'r') as zf:
                        zf.extractall(extracted_dir)
                    try:
                        os.remove(tmp_zip)
                    except:
                        pass
                    inf_files = glob.glob(os.path.join(extracted_dir, '**', '*.inf'), recursive=True)
                    if inf_files:
                        inf_path = inf_files[0]
            except Exception as e:
                log(f"Download/extract zip failed: {e}")
        # Fallback: direct INF from server
        if inf_path is None and SERVER_URL:
            try:
                url = SERVER_URL.rstrip('/') + '/drivers/VBCAudio.inf'
                tmp = os.path.join(base_dir, 'VBCAudio.inf')
                urllib.request.urlretrieve(url, tmp)
                if os.path.exists(tmp):
                    inf_path = tmp
            except Exception as e:
                log(f"Download driver failed: {e}")
        if inf_path is None:
            try:
                sio.emit('loopback_install_status', {'name': sid_name, 'status': 'missing'})
            except:
                pass
            return
        try:
            is_admin = False
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            except:
                is_admin = False
            if is_admin:
                cmd = ['pnputil', '/add-driver', inf_path, '/install']
                subprocess.run(cmd, check=False)
            else:
                ps = f"Start-Process pnputil -ArgumentList '/add-driver \"{inf_path}\" /install' -Verb runAs -Wait"
                subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps], check=False)
        except Exception as e:
            log(f"Driver install failed: {e}")
            try:
                sio.emit('loopback_install_status', {'name': sid_name, 'status': 'failed', 'error': str(e)})
            except:
                pass
            return
        try:
            rec2 = get_loopback_recorder(sr)
            if rec2 is None:
                sio.emit('loopback_install_status', {'name': sid_name, 'status': 'failed'})
                return
            sio.emit('loopback_enabled', {'name': sid_name})
            if extracted_dir:
                try:
                    shutil.rmtree(extracted_dir, ignore_errors=True)
                except:
                    pass
        except:
            pass
    except Exception as e:
        log(f"install_loopback error: {e}")
        try:
            sio.emit('loopback_install_status', {'name': employee_name, 'status': 'failed', 'error': str(e)})
        except:
            pass
def main():
    global SERVER_URL
    global was_just_updated
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
    was_just_updated = ("--updated" in sys.argv)
    
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
            
            first_capture = True
            audio_started = True
            frame_sent_count = 0
            
            # Start Mouse Thread
            def mouse_worker():
                while sio.connected:
                    try:
                        width, height = get_screen_size()
                        mx, my = get_mouse_pos()
                        px = mx / width if width else 0
                        py = my / height if height else 0
                        sio.emit('mouse_move', {'x': px, 'y': py})
                    except:
                        pass
                    time.sleep(0.1)
            
            threading.Thread(target=mouse_worker, daemon=True).start()

            last_img_str = None
            last_send_time = 0
            
            while sio.connected:
                # 1. Capture Screen
                frame = None
                img = None
                
                # Determine capture method
                # Default to dxcam if available and not failing too much
                if camera is None and dxcam is not None:
                    try:
                        camera = create_dxcam_camera()
                    except:
                        camera = None
                
                current_method = "dxcam" if (camera is not None and not first_capture) else "mss"
                
                if current_method == "dxcam":
                    try:
                        frame = camera.grab()
                        if frame is not None:
                            img = Image.fromarray(frame)
                            consecutive_empty_frames = 0
                        else:
                            # Static screen
                            consecutive_empty_frames += 1
                            if consecutive_empty_frames > 3000: # ~5 mins at 10fps check
                                log("Long idle, refreshing camera")
                                camera = create_dxcam_camera()
                                consecutive_empty_frames = 0
                    except Exception as e:
                        log(f"DXCam error: {e}")
                        camera = None # Force recreation or fallback
                        current_method = "mss"
                
                if current_method == "mss":
                    try:
                        monitors = sct.monitors
                        if monitors:
                            monitor = monitors[1] if len(monitors) > 1 else monitors[0]
                            sct_img = sct.grab(monitor)
                            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                    except Exception as e:
                        log(f"MSS error: {e}")
                        sio.sleep(1.0)
                
                if first_capture and img:
                    log(f"First capture successful via {current_method}")
                    first_capture = False

                # 2. Process & Send Image (if any)
                if img is not None:
                    try:
                        img.thumbnail((STREAM_MAX_WIDTH, STREAM_MAX_HEIGHT))
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
                        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        sio.emit('screen_share', {'image': img_str})
                        frame_sent_count += 1
                        if frame_sent_count % 100 == 0:
                            log(f"Screen frames sent: {frame_sent_count}")
                        last_img_str = img_str
                        last_send_time = time.time()
                    except Exception as e:
                        log(f"Error processing/sending image: {e}")
                elif last_img_str and (time.time() - last_send_time > 2.0):
                    # Heartbeat: Resend last frame if screen is static for > 2 seconds
                    # This ensures new server connections see the screen immediately
                    try:
                        sio.emit('screen_share', {'image': last_img_str})
                        last_send_time = time.time()
                    except:
                        pass
                
                if not audio_started:
                    def stream_audio(source):
                        sr = 48000
                        ch = 2 if source == 'system' else 1
                        try:
                            try:
                                ctypes.windll.ole32.CoInitialize(None)
                            except:
                                pass
                            try:
                                if comtypes:
                                    comtypes.CoInitialize()
                            except:
                                pass
                            try:
                                if pythoncom:
                                    pythoncom.CoInitialize()
                            except:
                                pass
                            if source == 'system':
                                log("Attempting system audio capture...")
                                rec = get_loopback_recorder(sr)
                                if rec is not None:
                                    log(f"Starting recording from: {rec}")
                                    try:
                                        sio.emit('loopback_enabled', {'name': employee_name})
                                    except:
                                        pass
                                    try:
                                        with rec:
                                            while sio.connected:
                                                data = rec.record(numframes=1024)
                                                if data is None:
                                                    continue
                                                if data.ndim == 1:
                                                    data = np.stack([data, data], axis=1)
                                                clipped = np.clip(data, -1.0, 1.0)
                                                interleaved = (clipped * 32767.0).astype(np.int16).flatten()
                                                payload = base64.b64encode(interleaved.tobytes()).decode('utf-8')
                                                sio.emit('audio_chunk', {'source': source, 'sr': sr, 'ch': 2, 'pcm': payload})
                                    except Exception as e:
                                        log(f"Soundcard capture error ({source}): {e}")
                                
                                # Fallback to sounddevice loopback
                                log("Soundcard loopback failed or not found. Trying sounddevice WASAPI loopback...")
                                if sd is not None:
                                    try:
                                        # Try to find default speakers and use loopback
                                        wasapi_dev = None
                                        try:
                                            default_out = sd.query_devices(kind='output')
                                            if default_out:
                                                wasapi_dev = default_out['index']
                                        except:
                                            pass
                                        
                                        if wasapi_dev is not None:
                                            log(f"Using sounddevice loopback on device {wasapi_dev}")
                                            try:
                                                sio.emit('loopback_enabled', {'name': employee_name})
                                            except:
                                                pass
                                                
                                            # WASAPI Loopback settings
                                            with sd.InputStream(device=wasapi_dev, channels=2, samplerate=sr,
                                                              dtype='float32',
                                                              extra_settings=sd.WasapiSettings(loopback=True)) as stream:
                                                while sio.connected:
                                                    data, _ = stream.read(1024)
                                                    if data is None:
                                                        continue
                                                    clipped = np.clip(data, -1.0, 1.0)
                                                    interleaved = (clipped * 32767.0).astype(np.int16).flatten()
                                                    payload = base64.b64encode(interleaved.tobytes()).decode('utf-8')
                                                    sio.emit('audio_chunk', {'source': source, 'sr': sr, 'ch': 2, 'pcm': payload})
                                    except Exception as e:
                                        log(f"Sounddevice loopback error: {e}")
                                        sio.emit('loopback_unavailable', {'name': employee_name, 'error': str(e)})
                                else:
                                    log("Sounddevice not available for fallback")
                                    sio.emit('loopback_unavailable', {'name': employee_name, 'error': "No audio library available"})
                            else:
                                if sd is not None:
                                    log("Mic capture: using sounddevice InputStream")
                                    with sd.InputStream(samplerate=sr, channels=1, dtype='float32') as stream:
                                        while sio.connected:
                                            data, _ = stream.read(1024)
                                            if data is None:
                                                continue
                                            mono = np.squeeze(data)
                                            clipped = np.clip(mono, -1.0, 1.0)
                                            interleaved = (clipped * 32767.0).astype(np.int16)
                                            payload = base64.b64encode(interleaved.tobytes()).decode('utf-8')
                                            sio.emit('audio_chunk', {'source': source, 'sr': sr, 'ch': 1, 'pcm': payload})
                                else:
                                    dev = sc.default_microphone()
                                    log("Mic capture: using soundcard default_microphone")
                                    if dev is None:
                                        return
                                    rec = dev.recorder(samplerate=sr)
                                    with rec:
                                        while sio.connected:
                                            data = rec.record(numframes=1024)
                                            if data is None:
                                                continue
                                            if data.ndim > 1:
                                                data = data[:,0]
                                            clipped = np.clip(data, -1.0, 1.0)
                                            interleaved = (clipped * 32767.0).astype(np.int16)
                                            payload = base64.b64encode(interleaved.tobytes()).decode('utf-8')
                                            sio.emit('audio_chunk', {'source': source, 'sr': sr, 'ch': 1, 'pcm': payload})
                        except Exception as e:
                            log(f"Audio stream error ({source}): {e}")
                    if sc is not None:
                        threading.Thread(target=stream_audio, args=('system',), daemon=True).start()
                    threading.Thread(target=stream_audio, args=('mic',), daemon=True).start()
                    audio_started = True
                sio.sleep(0.12)
                
        except Exception as e:
            log(f"Main loop error: {e}")
            time.sleep(5)  # Wait before retry

if __name__ == '__main__':
    main()
