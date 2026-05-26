import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
key = paramiko.RSAKey.from_private_key_file(r'tablet_key')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('127.0.0.1', port=8022, username='u0_a225', pkey=key, timeout=10)

sftp = c.open_sftp()
sftp.put(r'scripts\login_node.js', '/data/data/com.termux/files/home/aula-dashboard/login_node.js')
print("Pushed login_node.js")
sftp.close()
c.close()
