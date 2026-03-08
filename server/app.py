from flask import Flask, render_template, request, send_from_directory, jsonify, send_file, session, redirect, url_for, flash, Response
from flask_socketio import SocketIO, emit
# from flask_httpauth import HTTPBasicAuth # Deprecated in favor of login page
from werkzeug.security import generate_password_hash, check_password_hash
import os
import base64
import datetime
import threading
import time
from functools import wraps

import json
import sqlite3

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: opencv-python not installed. Recording disabled.")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
async_mode = 'threading' if os.name == 'nt' else 'eventlet'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode)
# auth = HTTPBasicAuth()

# Configuration
CONFIG_FILE = 'server_config.json'
DATABASE_FILE = 'monitoring.db'

def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clients
                 (original_name TEXT PRIMARY KEY, display_name TEXT, ip_address TEXT, last_seen TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def get_client_display_name(original_name):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT display_name FROM clients WHERE original_name=?", (original_name,))
    result = c.fetchone()
    conn.close()
    if result and result[0]:
        return result[0]
    return original_name

def update_client_info(original_name, ip_address, display_name=None):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    timestamp = datetime.datetime.now()
    
    # Check if exists
    c.execute("SELECT display_name FROM clients WHERE original_name=?", (original_name,))
    result = c.fetchone()
    
    if result:
        # Update
        if display_name:
             c.execute("UPDATE clients SET display_name=?, ip_address=?, last_seen=? WHERE original_name=?", 
                       (display_name, ip_address, timestamp, original_name))
        else:
             c.execute("UPDATE clients SET ip_address=?, last_seen=? WHERE original_name=?", 
                       (ip_address, timestamp, original_name))
    else:
        # Insert
        name_to_use = display_name if display_name else original_name
        c.execute("INSERT INTO clients (original_name, display_name, ip_address, last_seen) VALUES (?, ?, ?, ?)",
                  (original_name, name_to_use, ip_address, timestamp))
    
    conn.commit()
    conn.close()

def set_client_alias(original_name, new_alias):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE clients SET display_name=? WHERE original_name=?", (new_alias, original_name))
    conn.commit()
    conn.close()

def load_config():
    default_config = {
        'recordings_path': os.path.join(os.getcwd(), 'recordings'),
        'smb_username': '',
        'smb_password': '',
        'client_aliases': {}
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                # Merge defaults with loaded config (shallow merge)
                loaded = json.load(f)
                # Ensure client_aliases exists even if loading old config
                if 'client_aliases' not in loaded:
                    loaded['client_aliases'] = {}
                return {**default_config, **loaded}
        except Exception as e:
            print(f"Error loading config: {e}")
    return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def connect_smb(path, username, password):
    if not path.startswith(r'\\'):
        return True, "Local path"
        
    # Attempt to disconnect first to avoid conflicts
    os.system(f'net use "{path}" /delete /y >nul 2>&1')
    
    if username:
        # Connect with credentials
        cmd = f'net use "{path}" "{password}" /user:"{username}"'
    else:
        # Connect without explicit credentials (guest or current user)
        cmd = f'net use "{path}"'
        
    ret = os.system(cmd)
    if ret == 0:
        return True, "Connected successfully"
    else:
        return False, "Failed to connect to network share"

# Load initial config
server_config = load_config()
RECORDINGS_DIR = server_config['recordings_path']
CLIENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'client'))

# Try to connect if it's an SMB path
if RECORDINGS_DIR.startswith(r'\\'):
    connect_smb(RECORDINGS_DIR, server_config.get('smb_username'), server_config.get('smb_password'))

os.makedirs(RECORDINGS_DIR, exist_ok=True)
users = {
    "admin": generate_password_hash("password123")
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# @auth.verify_password
# def verify_password(username, password):
#     if username in users and check_password_hash(users.get(username), password):
#         return username
#     return None

# Store connected employees
employees = {}
# Store original hostnames: sid -> original_name
sid_to_original_name = {}
# Store IP addresses: sid -> ip_address
sid_to_ip = {}

# Store recording sessions: sid -> { 'writer': cv2.VideoWriter, 'filename': str, 'path': str, 'width': int, 'height': int }
recording_sessions = {}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in users and check_password_hash(users.get(username), password):
            session['username'] = username
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/config', methods=['GET', 'POST'])
@login_required
def handle_config():
    global RECORDINGS_DIR
    if request.method == 'POST':
        data = request.json
        new_path = data.get('recordings_path')
        smb_user = data.get('smb_username', '')
        smb_pass = data.get('smb_password', '')
        
        if new_path:
            # If SMB, try to connect first
            if new_path.startswith(r'\\'):
                success, msg = connect_smb(new_path, smb_user, smb_pass)
                if not success:
                    return jsonify({'success': False, 'error': f"SMB Connection failed: {msg}"}), 400
            
            # Update config
            server_config['recordings_path'] = new_path
            server_config['smb_username'] = smb_user
            server_config['smb_password'] = smb_pass
            
            save_config(server_config)
            
            # Update runtime variable and create dir
            RECORDINGS_DIR = new_path
            try:
                os.makedirs(RECORDINGS_DIR, exist_ok=True)
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
            
            safe_config = server_config.copy()
            safe_config['smb_password'] = ''
            return jsonify({'success': True, 'config': safe_config})
    
    # Don't send password back
    safe_config = server_config.copy()
    safe_config['smb_password'] = '' 
    return jsonify(safe_config)

@app.route('/')
@login_required
def index():
    return render_template('index.html', cv2_available=CV2_AVAILABLE)

@app.route('/recordings')
@login_required
def list_recordings():
    files = []
    try:
        for f in os.listdir(RECORDINGS_DIR):
            if f.endswith('.avi') or f.endswith('.mp4'):
                path = os.path.join(RECORDINGS_DIR, f)
                size = os.path.getsize(path)
                timestamp = os.path.getmtime(path)
                dt = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                files.append({'name': f, 'size': f"{size / (1024*1024):.2f} MB", 'date': dt})
    except Exception as e:
        print(f"Error listing recordings: {e}")
    return jsonify(files)

@app.route('/api/recordings/tree')
@login_required
def get_recordings_tree():
    """
    Returns a tree of recordings: Employee -> Date -> Hour -> File
    Structure:
    {
        "EmployeeName": {
            "2023-10-27": {
                "09": "filename.mp4",
                "10": "filename.mp4"
            }
        }
    }
    """
    tree = {}
    try:
        if not os.path.exists(RECORDINGS_DIR):
            return jsonify({})

        for emp_name in os.listdir(RECORDINGS_DIR):
            emp_path = os.path.join(RECORDINGS_DIR, emp_name)
            if not os.path.isdir(emp_path):
                continue
            
            tree[emp_name] = {}
            for date_str in os.listdir(emp_path):
                date_path = os.path.join(emp_path, date_str)
                if not os.path.isdir(date_path):
                    continue
                
                tree[emp_name][date_str] = []
                for file in os.listdir(date_path):
                    if file.endswith(('.mp4', '.avi')):
                        # file is like "09.avi" or "09-30-00.avi"
                        # We return a list of files for the day, let frontend sort/display
                        tree[emp_name][date_str].append(f"{emp_name}/{date_str}/{file}")
                        
    except Exception as e:
        print(f"Error building recordings tree: {e}")
        return jsonify({'error': str(e)}), 500
        
    return jsonify(tree)

@app.route('/download/client/<filename>')
# @auth.login_required - Client cannot authenticate easily for update
def download_client_update(filename):
    """
    Serve client update files.
    filename can be 'client.py' or 'SystemUpdate.exe'
    """
    try:
        # Check if requesting EXE from dist folder
        if filename.endswith('.exe'):
            dist_dir = os.path.join(CLIENT_DIR, 'dist')
            if os.path.exists(os.path.join(dist_dir, filename)):
                return send_from_directory(dist_dir, filename)
        
        # Default to client directory (source files)
        return send_from_directory(CLIENT_DIR, filename)
    except Exception as e:
        print(f"Error serving update file: {e}")
        return jsonify({'error': str(e)}), 404

@app.route('/api/video_metadata')
@login_required
def get_video_metadata():
    """
    Returns metadata for a video file (duration in seconds).
    Query param: filename (relative path)
    """
    if not CV2_AVAILABLE:
        return jsonify({'error': 'OpenCV not installed on server'}), 500

    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'Filename required'}), 400
        
    filepath = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
        
    try:
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
             return jsonify({'error': 'Could not open video file'}), 500

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return jsonify({
            'duration': duration,
            'fps': fps,
            'total_frames': frame_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/video_feed')
@login_required
def video_feed():
    """
    Streams an MJPEG feed from an AVI file.
    Query params: 
      - filename: relative path to the file
      - start: start time in seconds (default 0)
      - rate: playback rate (default 1.0)
    """
    if not CV2_AVAILABLE:
        return "OpenCV not installed", 500

    filename = request.args.get('filename')
    start_time = float(request.args.get('start', 0))
    rate = float(request.args.get('rate', 1.0))
    
    if not filename:
        return "Filename required", 400
        
    filepath = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(filepath):
        return "File not found", 404
        
    def generate():
        cap = cv2.VideoCapture(filepath)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps != fps: fps = 10.0
        
        # Seek to start
        start_frame = int(start_time * fps)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if start_frame < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        # Calculate delay based on rate
        # If rate is 1.0, delay is 1/fps
        # If rate is 2.0, delay is 0.5/fps
        delay = (1.0 / fps) / rate if rate > 0 else 0.1
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(delay)
        
        cap.release()
        
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/recordings/<path:filename>')
@login_required
def download_recording(filename):
    return send_from_directory(RECORDINGS_DIR, filename)

def get_recording_path(employee_name, sid, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    
    date_str = timestamp.strftime("%Y-%m-%d")
    hour_str = timestamp.strftime("%H")
    
    # Structure: Recordings/EmployeeName/Date/HH-MM-SS.avi
    # We use EmployeeName directly to group recordings.
    # Sanitize employee name to be safe for filesystem
    import re
    safe_emp_name = re.sub(r'[\\/*?:"<>|]', "", employee_name)
    safe_name = safe_emp_name # Removed SID suffix for consolidation
    emp_dir = os.path.join(RECORDINGS_DIR, safe_name)
    date_dir = os.path.join(emp_dir, date_str)
    
    os.makedirs(date_dir, exist_ok=True)
    
    filename = f"{timestamp.strftime('%H-%M-%S')}.avi"
    filepath = os.path.join(date_dir, filename)
    
    # Return relative path for URL and absolute for file ops
    return filepath, f"{safe_name}/{date_str}/{filename}"

def start_new_recording_segment(sid, employee_name):
    if sid in recording_sessions:
        # Close existing if open
        session = recording_sessions[sid]
        if session.get('writer'):
            session['writer'].release()
            print(f"Closed segment: {session['path']}")
    
    timestamp = datetime.datetime.now()
    filepath, rel_path = get_recording_path(employee_name, sid, timestamp)
    
    recording_sessions[sid] = {
        'writer': None,
        'filename': rel_path,
        'path': filepath,
        'width': 0,
        'height': 0,
        'start_hour': timestamp.hour,
        'last_frame': None
    }
    print(f"Started segment for {employee_name} ({sid}) -> {rel_path}")

def recording_loop():
    """Background task to write frames at fixed FPS"""
    while True:
        try:
            # target 10 FPS
            socketio.sleep(0.1)
            
            # Iterate over a copy of keys to avoid runtime errors
            for sid in list(recording_sessions.keys()):
                if sid not in recording_sessions:
                    continue
                    
                session = recording_sessions[sid]
                
                # Check for hour rotation
                current_hour = datetime.datetime.now().hour
                if current_hour != session.get('start_hour', -1):
                    # Rotate file
                    # We need the employee name. It's not in session, but we can get it from employees or store it.
                    # Assuming employees[sid] is available.
                    emp_name = employees.get(sid, 'Unknown')
                    start_new_recording_segment(sid, emp_name)
                    # The session object is replaced, so we continue to next iteration (or re-fetch)
                    continue

                frame = session.get('last_frame')
                if frame is None:
                    continue
                
                # Initialize writer if needed
                if session['writer'] is None:
                    height, width, layers = frame.shape
                    try:
                        fourcc = cv2.VideoWriter_fourcc(*'MJPG') 
                        session['writer'] = cv2.VideoWriter(session['path'], fourcc, 10.0, (width, height))
                        session['width'] = width
                        session['height'] = height
                    except Exception as e:
                        print(f"Error initializing writer for {sid}: {e}")
                        continue
                
                # Resize if needed
                if frame.shape[1] != session['width'] or frame.shape[0] != session['height']:
                    frame = cv2.resize(frame, (session['width'], session['height']))
                
                try:
                    session['writer'].write(frame)
                except Exception as e:
                    print(f"Error writing frame for {sid}: {e}")
                    
        except Exception as e:
            print(f"Error in recording loop: {e}")
            socketio.sleep(1)

# Start recording loop
socketio.start_background_task(recording_loop)

@socketio.on('connect')
def handle_connect():
    print('Client connected:', request.sid)
    # Store IP for deduplication
    sid_to_ip[request.sid] = request.remote_addr
    
    # Send current employee list to the newly connected client (dashboard)
    emit('employee_list_update', {
        'employees': employees, 
        'recording_status': {sid: (sid in recording_sessions) for sid in employees},
        'ip_addresses': sid_to_ip
    })

@socketio.on('register_employee')
def handle_register(data):
    """
    Employee client registers with a name.
    """
    original_name = data.get('name', 'Unknown')
    current_ip = request.remote_addr
    
    # Force store IP in case it was missed in connect
    sid_to_ip[request.sid] = current_ip
    print(f"DEBUG: Registering client {original_name} from IP: {current_ip}")
    
    # Aggressive Deduplication Strategy
    # 1. Same IP: Assumes one client per machine. Handles restarts where PID/Name changes.
    # 2. Same Name: Handles cases where IP changes but Identity is same (unless Unknown).
    
    for sid in list(employees.keys()):
        if sid == request.sid:
            continue
            
        should_remove = False
        old_ip = sid_to_ip.get(sid)
        old_name = sid_to_original_name.get(sid)
        
        # Rule 1: Same IP Address (Strongest signal for "Same Machine")
        if old_ip == current_ip:
            should_remove = True
            
        # Rule 2: Same Name (Identity persistence), ignore if both are generic 'Unknown'
        elif old_name == original_name and original_name != 'Unknown':
            should_remove = True
            
        if should_remove:
            print(f"Removing duplicate/stale session (Match: IP={old_ip==current_ip}, Name={old_name==original_name})")
            print(f"  Old: {old_name} ({sid}) @ {old_ip}")
            print(f"  New: {original_name} ({request.sid}) @ {current_ip}")
            
            if sid in employees:
                del employees[sid]
            
            if sid in sid_to_original_name:
                del sid_to_original_name[sid]
                
            if sid in sid_to_ip:
                del sid_to_ip[sid]
            
            stop_recording_for_sid(sid)

    sid_to_original_name[request.sid] = original_name
    
    # Update DB and get display name
    update_client_info(original_name, current_ip)
    display_name = get_client_display_name(original_name)
    
    employees[request.sid] = display_name
    print(f'Employee registered: {display_name} (Original: {original_name}, SID: {request.sid})')
    
    # Notify CEO (and other clients) about the new employee
    # Also send recording status
    is_recording = request.sid in recording_sessions
    emit('employee_list_update', {
        'employees': employees, 
        'recording_status': {sid: (sid in recording_sessions) for sid in employees},
        'ip_addresses': sid_to_ip
    }, broadcast=True)

@socketio.on('rename_client')
def handle_rename_client(data):
    """
    Admin renames a client.
    """
    target_sid = data.get('sid')
    new_name = data.get('new_name')
    
    print(f"DEBUG: Rename request received - SID: {target_sid}, New Name: {new_name}")
    print(f"DEBUG: Current sid_to_original_name: {sid_to_original_name}")
    print(f"DEBUG: Current employees: {employees}")
    
    if target_sid and new_name and target_sid in sid_to_original_name:
        original_name = sid_to_original_name[target_sid]
        
        # We need to know the CURRENT name to find the folder, because the folder is named after the current display name (if we already renamed it before)
        # However, sid_to_original_name stores the HARDWARE name.
        # But wait, our `get_recording_path` uses `employee_name` which comes from `employees[sid]`.
        # `employees[sid]` holds the DISPLAY name (alias).
        # So if we rename "IMON" -> "Reception", the folder should be renamed from "IMON" to "Reception".
        
        current_display_name = employees.get(target_sid, original_name)
        
        print(f"DEBUG: Found original name: {original_name} for SID: {target_sid}")
        
        # Update Database
        try:
            set_client_alias(original_name, new_name)
            print(f"DEBUG: Database alias set: {original_name} -> {new_name}")
        except Exception as e:
            print(f"ERROR: Database update failed: {e}")
            return
            
        # Update Directory Name
        # We sanitize names same as get_recording_path
        import re
        safe_old_name = re.sub(r'[\\/*?:"<>|]', "", current_display_name)
        safe_new_name = re.sub(r'[\\/*?:"<>|]', "", new_name)
        
        old_dir = os.path.join(RECORDINGS_DIR, safe_old_name)
        new_dir = os.path.join(RECORDINGS_DIR, safe_new_name)
        
        if os.path.exists(old_dir) and safe_old_name != safe_new_name:
            try:
                # If target exists, we have a conflict. Merge?
                if os.path.exists(new_dir):
                    print(f"DEBUG: Target directory {new_dir} already exists. Attempting merge.")
                    # Move all files from old to new
                    import shutil
                    for item in os.listdir(old_dir):
                        s = os.path.join(old_dir, item)
                        d = os.path.join(new_dir, item)
                        if os.path.isdir(s):
                            # Date folder
                            if os.path.exists(d):
                                # Merge date folder
                                for file in os.listdir(s):
                                    shutil.move(os.path.join(s, file), os.path.join(d, file))
                                os.rmdir(s) # Remove empty date folder
                            else:
                                shutil.move(s, d)
                        else:
                            shutil.move(s, d)
                    os.rmdir(old_dir) # Remove old root
                    print(f"Merged {old_dir} into {new_dir}")
                else:
                    os.rename(old_dir, new_dir)
                    print(f"Renamed directory {old_dir} to {new_dir}")
            except Exception as e:
                print(f"ERROR: Failed to rename directory: {e}")
        
        # Update runtime
        employees[target_sid] = new_name
        
        print(f"DEBUG: Updated employees dict: {employees}")
        
        # Broadcast update
        emit('employee_list_update', {
            'employees': employees, 
            'recording_status': {sid: (sid in recording_sessions) for sid in employees},
            'ip_addresses': sid_to_ip
        }, broadcast=True)
        
        print(f"Renamed client {original_name} to {new_name}")
    else:
        print(f"DEBUG: Invalid rename request or missing SID in map.")
        print(f"DEBUG: Request SID: {target_sid}")
        print(f"DEBUG: New Name: {new_name}")
        print(f"DEBUG: SID in map: {target_sid in sid_to_original_name}")
        if target_sid in employees:
            print(f"DEBUG: SID found in employees, but not in original_name map. Attempting fallback.")
            # Fallback: Assume current name is original if map is missing (should not happen normally)
            # Or recover from DB if possible?
            # For now, just try to update runtime
            employees[target_sid] = new_name
            emit('employee_list_update', {
                'employees': employees, 
                'recording_status': {sid: (sid in recording_sessions) for sid in employees},
                'ip_addresses': sid_to_ip
            }, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in employees:
        print(f'Employee disconnected: {employees[request.sid]}')
        del employees[request.sid]
        if request.sid in sid_to_original_name:
            del sid_to_original_name[request.sid]
        
        if request.sid in sid_to_ip:
            del sid_to_ip[request.sid]
        
        # Stop recording if active
        stop_recording_for_sid(request.sid)
        
        # Notify CEO about the disconnection
        emit('employee_list_update', {'employees': employees, 'recording_status': {sid: (sid in recording_sessions) for sid in employees}}, broadcast=True)
    print('Client disconnected:', request.sid)

def stop_recording_for_sid(sid):
    if sid in recording_sessions:
        session = recording_sessions[sid]
        if session.get('writer'):
            session['writer'].release()
        print(f"Stopped recording for {sid}. Saved to {session['path']}")
        del recording_sessions[sid]

@socketio.on('start_recording')
def handle_start_recording(data):
    if not CV2_AVAILABLE:
        return
    
    target_sid = data.get('sid')
    if target_sid and target_sid in employees and target_sid not in recording_sessions:
        employee_name = employees[target_sid]
        start_new_recording_segment(target_sid, employee_name)
        emit('recording_started', {'sid': target_sid}, broadcast=True)

@socketio.on('stop_recording')
def handle_stop_recording(data):
    if not CV2_AVAILABLE:
        return

    target_sid = data.get('sid')
    if target_sid:
        stop_recording_for_sid(target_sid)
        emit('recording_stopped', {'sid': target_sid}, broadcast=True)

@socketio.on('force_update_client')
def handle_force_update(data):
    """
    Admin requests a client to update.
    """
    target_sid = data.get('sid')
    if target_sid and target_sid in employees:
        print(f"Sending update command to {employees[target_sid]} ({target_sid})")
        emit('perform_update', {}, room=target_sid)

@socketio.on('screen_share')
def handle_screen_share(data):
    """
    Employee client sends screen data (base64 image).
    Server broadcasts it to the CEO dashboard.
    """
    sid = request.sid
    data['sid'] = sid
    data['name'] = employees.get(sid, 'Unknown')
    emit('update_screen', data, broadcast=True)
    
    # Handle recording
    if CV2_AVAILABLE and sid in recording_sessions:
        try:
            session = recording_sessions[sid]
            
            # Decode image
            image_data = base64.b64decode(data['image'])
            np_arr = np.frombuffer(image_data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                # Store the latest frame for the background recording loop
                session['last_frame'] = frame
                
        except Exception as e:
            print(f"Error processing frame for recording {sid}: {e}")

@socketio.on('mouse_move')
def handle_mouse_move(data):
    """
    Broadcast mouse coordinates.
    data: {'x': 0.5, 'y': 0.5} (percentages)
    """
    data['sid'] = request.sid
    emit('update_mouse', data, broadcast=True)

if __name__ == '__main__':
    print("Starting secure iMon Server on port 5000 (Eventlet)...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
