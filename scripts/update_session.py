"""
Update Aula session cookies on the Android tablet.
Run this on PC after getting fresh cookies from aula.dk (F12 -> Application -> Cookies).

Usage: python update_session.py <PHPSESSID> <Csrfp-Token>
"""
import sys
import json
import paramiko

TABLET_PORT = 8022
TABLET_USER = "u0_a225"
KEY_FILE = r"C:\Users\rnf\Projects\aula-dashboard\tablet_key"
REMOTE_SESSION = "/data/data/com.termux/files/home/aula-dashboard/session.json"

def get_tablet_ip():
    import subprocess
    r = subprocess.run(["adb", "forward", "tcp:8022", "tcp:8022"], capture_output=True, text=True)
    return "127.0.0.1"  # always via ADB tunnel

def connect(ip):
    key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
    return c

def update_session(phpsessid, csrf_token):
    ip = get_tablet_ip()
    c = connect(ip)
    sftp = c.open_sftp()

    session = {"PHPSESSID": phpsessid, "CSRF_TOKEN": csrf_token}
    with sftp.open(REMOTE_SESSION, "w") as f:
        f.write(json.dumps(session, indent=2))
    sftp.close()

    # Restart server to pick up new session
    _, out, _ = c.exec_command("pkill -f uvicorn; sleep 1; cd ~/aula-dashboard && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 & sleep 3 && curl -s http://localhost:8000/api/status", timeout=15)
    print(out.read().decode())
    c.close()
    print("Session updated and server restarted.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python update_session.py <PHPSESSID> <Csrfp-Token>")
        sys.exit(1)
    update_session(sys.argv[1], sys.argv[2])
