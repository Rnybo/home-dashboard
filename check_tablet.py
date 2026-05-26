import paramiko, subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
subprocess.run(['adb', 'forward', 'tcp:8022', 'tcp:8022'], capture_output=True)
key = paramiko.RSAKey.from_private_key_file(r'tablet_key')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('127.0.0.1', port=8022, username='u0_a225', pkey=key, timeout=10)

def ssh(cmd, timeout=300):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o: print(o)
    if e: print("ERR:", e)

print("Stopper og sletter alt...")
ssh("pkill -9 -f uvicorn 2>/dev/null; pkill -9 -f python 2>/dev/null; echo stopped")
ssh("rm -rf ~/aula-dashboard ~/home-dashboard ~/start_server.sh ~/.familieoverblik_installed; echo deleted")
ssh("ls ~/ | grep -E 'dashboard|server'")  # verificer slettet

print("Kører install.sh fra home-dashboard repo...")
ssh("curl -sSL https://raw.githubusercontent.com/Rnybo/home-dashboard/main/scripts/install.sh | bash")

print("Pusher .env...")
sftp = c.open_sftp()
sftp.put(r'.env', '/data/data/com.termux/files/home/home-dashboard/.env')
sftp.close()
print(".env pushet")

print("Verificerer...")
ssh("ls ~/home-dashboard/")
ssh("curl -s http://127.0.0.1:8000/api/config", timeout=10)
c.close()
