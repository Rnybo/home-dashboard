"""SSH helper for Termux on Android tablet"""
import paramiko
import sys

TABLET_IP = "127.0.0.1"
TABLET_PORT = 8022
TABLET_USER = "u0_a225"
KEY_FILE = r"C:\Users\rnf\Projects\aula-dashboard\tablet_key"

def ssh_run(cmd: str, timeout: int = 180) -> str:
    key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
    _, out, err = c.exec_command(cmd, timeout=timeout)
    stdout = out.read().decode('utf-8', errors='replace')
    stderr = err.read().decode('utf-8', errors='replace')
    c.close()
    return stdout + (f"\nSTDERR: {stderr}" if stderr.strip() else "")

def ssh_push(local_path: str, remote_path: str):
    key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
    sftp = c.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    c.close()
    print(f"Pushed {local_path} -> {remote_path}")

if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "echo hello && python3 --version"
    print(ssh_run(cmd))
