"""
gen_ssh_key.py
Generate RSA SSH key pair for PC→tablet connection.
Creates: tablet_key (private) and tablet_key.pub (public)
"""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
priv = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption())
pub = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)

with open("tablet_key", "wb") as f:
    f.write(priv)
with open("tablet_key.pub", "wb") as f:
    f.write(pub + b"\n")

print("Generated tablet_key and tablet_key.pub")
print("Now run:")
print("  adb push tablet_key.pub /sdcard/tablet_key.pub")
print("Then in Termux:")
print("  mkdir -p ~/.ssh && cat /sdcard/tablet_key.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys")
