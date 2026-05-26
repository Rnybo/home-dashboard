"""Full sync of all relevant project files to Android tablet"""
import paramiko
import os

TABLET_IP = "127.0.0.1"
TABLET_PORT = 8022
TABLET_USER = "u0_a225"
KEY_FILE = r"C:\Users\rnf\Projects\aula-dashboard\tablet_key"
LOCAL_ROOT = r"C:\Users\rnf\Projects\aula-dashboard"
REMOTE_ROOT = "/data/data/com.termux/files/home/aula-dashboard"

# All files to deploy: (local, remote)
FILES = [
    ("main.py",                    "main.py"),
    ("aula_client.py",             "aula_client.py"),
    ("aula_playwright_android.py", "aula_playwright.py"),  # stub for Android
    ("login_node.js",              "login_node.js"),
    ("requirements.txt",           "requirements.txt"),
    (".env",                       ".env"),
    ("static/index.html",          "static/index.html"),
]

def connect():
    key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
    return c

def ssh_run(c, cmd, timeout=15):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    return out.read().decode() + err.read().decode()

c = connect()
sftp = c.open_sftp()

# Ensure dirs exist
ssh_run(c, f"mkdir -p {REMOTE_ROOT}/static {REMOTE_ROOT}/debug_screenshots")

# Remove stale nested aula-dashboard folder
ssh_run(c, f"rm -rf {REMOTE_ROOT}/aula-dashboard")

# Remove old renew.html
ssh_run(c, f"rm -f {REMOTE_ROOT}/static/renew.html")

# Push all files
for local_file, remote_file in FILES:
    local_path = os.path.join(LOCAL_ROOT, local_file)
    remote_path = f"{REMOTE_ROOT}/{remote_file}"
    sftp.put(local_path, remote_path)
    print(f"  pushed {local_file}")

sftp.close()

# Clear pycache
ssh_run(c, f"rm -rf {REMOTE_ROOT}/__pycache__")

# Verify key files
result = ssh_run(c, f"md5sum {REMOTE_ROOT}/main.py {REMOTE_ROOT}/aula_playwright.py {REMOTE_ROOT}/login_node.js {REMOTE_ROOT}/static/index.html")
print(result)

c.close()
print("Full sync complete.")
