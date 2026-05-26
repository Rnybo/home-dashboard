import paramiko, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
subprocess.run(['adb', 'forward', 'tcp:8022', 'tcp:8022'], capture_output=True)
key = paramiko.RSAKey.from_private_key_file(r'tablet_key')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('127.0.0.1', port=8022, username='u0_a225', pkey=key, timeout=10)
def ssh(cmd, timeout=15):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    return out.read().decode('utf-8', errors='replace').strip()

API = "f72c6ce05d9493daecebb1683c91db6675a3ba09efe384416330df7060f21e44"
result = ssh(f"""python3 -c "
import json, urllib.request
req = urllib.request.Request('http://127.0.0.1:8000/api/posts?inst_profile_ids=5620584,5620590&limit=50')
req.add_header('x-api-key', '{API}')
data = json.loads(urllib.request.urlopen(req).read())
posts = data.get('posts', [])
for p in posts:
    atts = p.get('attachments', [])
    for a in atts:
        name = a.get('name','') or ''
        if any(name.lower().endswith(ext) for ext in ['.pdf','.doc','.docx','.xls','.xlsx']):
            print('POST:', p.get('title','')[:50])
            print('FULL ATT:', json.dumps(a, indent=2)[:600])
            break
" """)
print(result[:4000] or "No file attachments found in first 50 posts")
c.close()
