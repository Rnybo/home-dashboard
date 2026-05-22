"""Send start command to Termux via ADB keystrokes"""
import subprocess, time

def adb(args):
    subprocess.run(['adb'] + args, capture_output=True)

def send_text(text):
    """Send text avoiding space issues by writing to file first"""
    # Write command to file
    escaped = text.replace("'", "\\'")
    subprocess.run(['adb', 'shell', f"printf '%s' '{escaped}' > /sdcard/_cmd.sh"], capture_output=True)
    time.sleep(0.3)

# Focus Termux
adb(['shell', 'am', 'start', '-n', 'com.termux/.HomeActivity'])
time.sleep(2)

# Send the command via clipboard paste approach
cmd = "bash /sdcard/start_server.sh"

# Type each character
for char in cmd:
    if char == ' ':
        adb(['shell', 'input', 'keyevent', '62'])
    elif char == '/':
        adb(['shell', 'input', 'keyevent', '76'])
    elif char == '_':
        adb(['shell', 'input', 'text', '_'])
    elif char == '.':
        adb(['shell', 'input', 'keyevent', '56'])
    else:
        adb(['shell', 'input', 'text', char])

adb(['shell', 'input', 'keyevent', '66'])  # Enter
print("Command sent to Termux")
time.sleep(4)

# Check
r = subprocess.run(['adb', 'shell', 'ss -tlnp 2>/dev/null | grep 8000'], capture_output=True, text=True)
print("Port 8000:", r.stdout.strip() or "not listening")
