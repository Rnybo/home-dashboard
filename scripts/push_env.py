import paramiko

TABLET_IP = "127.0.0.1"; TABLET_PORT = 8022; TABLET_USER = "u0_a225"
KEY_FILE = r"C:\Users\rnf\Projects\aula-dashboard\tablet_key"

key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
sftp = c.open_sftp()
sftp.put(r"C:\Users\rnf\Projects\aula-dashboard\.env",
         "/data/data/com.termux/files/home/aula-dashboard/.env")
sftp.close()
_, out, _ = c.exec_command("grep MITID ~/aula-dashboard/.env", timeout=5)
print(out.read().decode())
c.close()
