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

# Slet ALT inkl. marker og gammel home-dashboard
ssh("pkill -9 -f uvicorn 2>/dev/null; rm -rf ~/home-dashboard ~/aula-dashboard ~/.familieoverblik_installed; echo cleaned")
ssh("ls ~/ | grep -E 'dashboard|installed'")  # verificer

# Kør frisk install
ssh("curl -sSL https://raw.githubusercontent.com/Rnybo/home-dashboard/main/scripts/install.sh | bash")

# Tjek om git clone virkede
ssh("ls ~/home-dashboard/backend/ 2>/dev/null || echo MISSING")

# Push .env og genstart
sftp = c.open_sftp()
sftp.put(r'.env', '/data/data/com.termux/files/home/home-dashboard/.env')
sftp.close()
print(".env pushet")
ssh("pkill -f uvicorn 2>/dev/null; sleep 1")
c.exec_command("cd ~/home-dashboard && nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> server.log 2>&1 &", timeout=3)
time.sleep(6)
ssh("curl -s http://127.0.0.1:8000/api/config", timeout=10)
c.close()
