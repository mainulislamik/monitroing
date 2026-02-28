import socket
import os

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
    print(f"Updated client/client.py with Server IP: {ip}")

if __name__ == "__main__":
    ip = get_ip()
    print(f"Detected IP: {ip}")
    user_ip = input(f"Press Enter to use {ip}, or type the correct Server IP (like 192.168.5.104): ").strip()
    if user_ip:
        ip = user_ip

    update_client_ip(ip)
