"""
patch_playwright_all.py
Patch playwright-core on Android tablet to support the android platform.
Run this after: npm install playwright-core@1.52.0
"""
import paramiko

TABLET_IP = "127.0.0.1"
TABLET_PORT = 8022
TABLET_USER = "u0_a225"
KEY_FILE = r"C:\Users\rnf\Projects\aula-dashboard\tablet_key"
BASE = "/data/data/com.termux/files/home/aula-dashboard/node_modules/playwright-core"

key = paramiko.RSAKey.from_private_key_file(KEY_FILE)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(TABLET_IP, port=TABLET_PORT, username=TABLET_USER, pkey=key, timeout=10)
sftp = c.open_sftp()

def patch(path, old, new, label):
    try:
        with sftp.open(path, 'rb') as f:
            content = f.read().decode('utf-8')
        if old in content:
            with sftp.open(path, 'wb') as f:
                f.write(content.replace(old, new, 1).encode('utf-8'))
            print(f"  PATCHED: {label}")
        elif new in content:
            print(f"  already patched: {label}")
        else:
            print(f"  NOT FOUND: {label}")
    except Exception as e:
        print(f"  ERROR {label}: {e}")

# Patch 1: hostPlatform.js — treat android as ubuntu22.04-arm64
patch(
    f"{BASE}/lib/server/utils/hostPlatform.js",
    "    hostPlatform: '<unknown>',",
    "    hostPlatform: 'ubuntu22.04-arm64',",
    "hostPlatform <unknown> → ubuntu22.04-arm64"
)

# Patch 2: registry/index.js — allow android in cache dir check
patch(
    f"{BASE}/lib/server/registry/index.js",
    'if (process.platform === "linux")',
    'if (process.platform === "linux" || process.platform === "android")',
    "registry cache dir android support"
)

sftp.close()
c.close()
print("Done.")
