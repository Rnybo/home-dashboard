"""Sync latest code to Android tablet via git pull + restart"""
import subprocess, time, paramiko, sys
from pathlib import Path

TABLET_IP = "127.0.0.1"
TABLET_PORT = 8022
TABLET_USER = "u0_a225"
KEY_FILE = str(Path(__file__).parent.parent / "tablet_key")

def connect():
    subprocess.run(['adb', 'forward', 'tcp:8022', 'tcp:8022'], capture_output=True)
    key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
    return c

def ssh(c, cmd, timeout=60):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o: print(o)
    if e: print("ERR:", e)
    return o

def push_file(c, local, remote):
    sftp = c.open_sftp()
    sftp.put(local, remote)
    sftp.close()
    print(f"  pushed {local}")

if __name__ == "__main__":
    c = connect()

    # Pull latest code
    print("Pulling latest code...")
    ssh(c, "cd ~/aula-dashboard && git pull origin main")

    # Push .env (never in git)
    push_file(c, ".env", "/data/data/com.termux/files/home/aula-dashboard/.env")

    # Restart server
    print("Restarting server...")
    ssh(c, "pkill -f uvicorn 2>/dev/null; sleep 1")
    ssh(c, "cd ~/aula-dashboard && rm -rf backend/__pycache__ && "
           "nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &")
    time.sleep(4)

    # Verify
    result = ssh(c, "curl -s http://127.0.0.1:8000/api/config", timeout=10)
    if "api_key" in result:
        print("Server running OK")
    else:
        print("WARNING: server may not be running — check server.log")

    c.close()
