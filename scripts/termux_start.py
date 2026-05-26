"""
termux_start.py
Start/restart the uvicorn server on the Android tablet.
Requires: adb forward tcp:8022 tcp:8022 (done automatically)
"""
import subprocess, time, paramiko

TABLET_IP = "127.0.0.1"
TABLET_PORT = 8022
TABLET_USER = "u0_a225"
KEY_FILE = r"C:\Users\rnf\Projects\aula-dashboard\tablet_key"

def adb(args):
    subprocess.run(['adb'] + args, capture_output=True)

def start_server():
    # Ensure ADB forward is active
    adb(['forward', 'tcp:8022', 'tcp:8022'])

    key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)

    # Kill old server
    c.exec_command('pkill -f uvicorn 2>/dev/null', timeout=5)
    time.sleep(2)

    # Start new server — nohup keeps it alive after SSH closes
    c.exec_command(
        'cd ~/aula-dashboard && rm -f __pycache__/*.pyc && '
        'nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &',
        timeout=5
    )
    c.close()

    time.sleep(4)

    # Verify
    r = subprocess.run(['adb', 'shell', 'ss -tlnp 2>/dev/null | grep 8000'],
                       capture_output=True, text=True)
    if '8000' in r.stdout:
        print("Server running on port 8000")
    else:
        print("WARNING: port 8000 not listening — check server.log on tablet")

if __name__ == "__main__":
    start_server()
