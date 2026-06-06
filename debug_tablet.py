import paramiko
k = paramiko.Ed25519Key.from_private_key_file('tablet_key')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('127.0.0.1', port=8022, username='u0_a163', pkey=k, timeout=10)

cmds = [
    'cd ~/home-dashboard && python -c "from backend.aula_lib.auth.mitid_client import MitIDAuthClient; print(\'import OK\')" 2>&1',
    'cd ~/home-dashboard && python -c "import sys; print(sys.path)" 2>&1',
    'ls ~/home-dashboard/backend/aula_lib/',
]
for cmd in cmds:
    _, out, err = c.exec_command(cmd)
    print(f"CMD: {cmd[:60]}")
    print(out.read().decode())
    print(err.read().decode())
    print()
c.close()
