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

ssh("cat ~/aula-dashboard/session.json")
print("---")
ssh("curl -s http://127.0.0.1:8000/api/status -H 'x-api-key: f72c6ce05d9493daecebb1683c91db6675a3ba09efe384416330df7060f21e44'", timeout=10)
c.close()
