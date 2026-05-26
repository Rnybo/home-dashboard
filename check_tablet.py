import paramiko, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
subprocess.run(['adb', 'forward', 'tcp:8022', 'tcp:8022'], capture_output=True)
key = paramiko.RSAKey.from_private_key_file(r'tablet_key')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('127.0.0.1', port=8022, username='u0_a225', pkey=key, timeout=10)

def ssh(cmd, timeout=15):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o: print(o)
    if e: print("ERR:", e)

ssh("cat ~/aula-dashboard/server.log")
print("---PGREP---")
ssh("pgrep -fa uvicorn")
print("---MANUAL TEST---")
ssh("cd ~/aula-dashboard && python -c 'from backend.main import app; print(\"import OK\")'")
c.close()
