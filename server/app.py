from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
async_mode = 'threading' if os.name == 'nt' else 'eventlet'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode)
auth = HTTPBasicAuth()

# Basic authentication credentials
users = {
    "admin": generate_password_hash("password123")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

# Store connected employees
employees = {}

@app.route('/')
@auth.login_required
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected:', request.sid)

@socketio.on('register_employee')
def handle_register(data):
    """
    Employee client registers with a name.
    """
    employee_name = data.get('name', 'Unknown')
    employees[request.sid] = employee_name
    print(f'Employee registered: {employee_name} ({request.sid})')
    # Notify CEO (and other clients) about the new employee
    emit('employee_list_update', employees, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in employees:
        print(f'Employee disconnected: {employees[request.sid]}')
        del employees[request.sid]
        # Notify CEO about the disconnection
        emit('employee_list_update', employees, broadcast=True)
    print('Client disconnected:', request.sid)

@socketio.on('screen_share')
def handle_screen_share(data):
    """
    Employee client sends screen data (base64 image).
    Server broadcasts it to the CEO dashboard.
    """
    data['sid'] = request.sid
    data['name'] = employees.get(request.sid, 'Unknown')
    emit('update_screen', data, broadcast=True)

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
