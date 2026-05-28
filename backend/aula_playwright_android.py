"""
Android implementation of AulaPlaywright.
Uses login_node.js (Node.js + system Chromium) instead of Python Playwright.
"""
import base64
import json
import logging
import os
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

NODE_SCRIPT = Path(__file__).parent.parent / "scripts" / "login_node.js"
CHROMIUM_PATH = "/data/data/com.termux/files/usr/bin/chromium-browser"


class AulaLoginState:
    IDLE = "idle"
    RUNNING = "running"
    SHOW_QR = "show_qr"
    SUCCESS = "success"
    FAILED = "failed"


class AulaPlaywright:
    def __init__(self, on_success):
        self.on_success = on_success
        self.state = AulaLoginState.IDLE
        self.error = None
        self.qr_image = None
        self._proc = None
        self._thread = None

    def get_status(self):
        return {"state": self.state, "error": self.error, "qr_image": self.qr_image}

    def start_login(self, account_index: int = 0):
        if self.state in (AulaLoginState.RUNNING, AulaLoginState.SHOW_QR):
            logger.info("Login already in progress")
            return
        self.state = AulaLoginState.RUNNING
        self.error = None
        self.qr_image = None
        self._account_index = account_index
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
        self.state = AulaLoginState.IDLE
        self.error = None
        self.qr_image = None

    def _run(self):
        # Build account list from env
        accounts = []
        for suffix in ["", "_2", "_3", "_4", "_5"]:
            u = os.getenv(f"MITID_USERNAME{suffix}", "")
            i = os.getenv(f"MITID_IDENTITY{suffix}", "")
            if u:
                accounts.append({"username": u, "identity": i})

        if not accounts:
            self.state = AulaLoginState.FAILED
            self.error = "MITID_USERNAME not set in .env"
            return

        idx = getattr(self, "_account_index", 0)
        if idx >= len(accounts):
            idx = 0
        account = accounts[idx]

        env = os.environ.copy()
        env["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = "ubuntu22.04-arm64"
        env["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = CHROMIUM_PATH
        # Chromium needs a writable tmp dir on Android
        termux_tmp = "/data/data/com.termux/files/usr/tmp"
        env["TMPDIR"] = termux_tmp
        env["XDG_RUNTIME_DIR"] = termux_tmp

        try:
            self._proc = subprocess.Popen(
                ["node", str(NODE_SCRIPT), account["username"], account["identity"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(NODE_SCRIPT.parent),
                env=env,
            )

            # Read stderr in a thread to capture QR images while waiting
            def read_stderr():
                for raw_line in self._proc.stderr:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line.startswith("QR_IMAGE_BASE64:"):
                        self.qr_image = line[len("QR_IMAGE_BASE64:"):]
                        self.state = AulaLoginState.SHOW_QR
                    elif line.startswith("LOGIN_ERROR:"):
                        self.error = line[len("LOGIN_ERROR:"):]
                    else:
                        logger.info(f"[node] {line}")

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Read stdout (the JSON result)
            stdout = self._proc.stdout.read().decode("utf-8", errors="replace").strip()
            self._proc.wait()
            stderr_thread.join(timeout=2)

            if self._proc.returncode != 0:
                self.state = AulaLoginState.FAILED
                self.error = self.error or f"node exited with code {self._proc.returncode}"
                logger.error(f"Login failed: {self.error}")
                return

            result = json.loads(stdout)
            phpsessid = result.get("PHPSESSID")
            csrf = result.get("CSRF_TOKEN")

            if not phpsessid or not csrf:
                raise ValueError(f"Missing cookies in output: {result}")

            self.on_success(phpsessid, csrf)
            self.state = AulaLoginState.SUCCESS
            self.qr_image = None
            logger.info("Login successful — session updated")

        except Exception as e:
            self.state = AulaLoginState.FAILED
            self.error = str(e)
            logger.error(f"Login error: {e}", exc_info=True)
