"""Deploy updated project files to Android tablet via SSH"""
import paramiko
import os

TABLET_IP = "127.0.0.1"
TABLET_PORT = 8022
TABLET_USER = "u0_a225"
KEY_FILE = r"C:\Users\rnf\Projects\aula-dashboard\tablet_key"
LOCAL_ROOT = r"C:\Users\rnf\Projects\aula-dashboard"
REMOTE_ROOT = "/data/data/com.termux/files/home/aula-dashboard"

FILES = [
    ("main.py",                      "main.py"),
    ("aula_client.py",               "aula_client.py"),
    ("aula_playwright_android.py",   "aula_playwright.py"),
    ("login_node.js",                "login_node.js"),
    ("static/index.html",            "static/index.html"),
]

def connect():
    key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
    return c

def ssh_run(c, cmd, timeout=30):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    stdout = out.read().decode()
    stderr = err.read().decode()
    return stdout + (f"\nSTDERR: {stderr}" if stderr.strip() else "")

c = connect()
sftp = c.open_sftp()
ssh_run(c, f"mkdir -p {REMOTE_ROOT}/static")

for local_file, remote_file in FILES:
    sftp.put(os.path.join(LOCAL_ROOT, local_file), f"{REMOTE_ROOT}/{remote_file}")
    print(f"  pushed {local_file} -> {remote_file}")

sftp.close()

print(ssh_run(c, f"rm -rf {REMOTE_ROOT}/__pycache__"))
print(ssh_run(c, "pkill -f uvicorn 2>/dev/null; sleep 1; echo killed"))
print(ssh_run(c, f"cd {REMOTE_ROOT} && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 & echo $! > server.pid && sleep 3 && tail -5 server.log"))
c.close()
print("Deploy complete.")
