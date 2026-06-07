"""
aula_auth.py — MitID authentication via nickknissen/aula library.

Replaces aula_playwright.py. Uses OAuth2 PKCE + SAML flow (no browser/Playwright).
First login requires MitID app approval or QR scan.
Subsequent logins use refresh_token automatically — no user interaction needed.
"""

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("uvicorn.error")

ROOT = Path(__file__).parent.parent
TOKENS_FILE = ROOT / "tokens.json"


class AulaLoginState:
    IDLE = "idle"
    RUNNING = "running"
    SHOW_QR = "show_qr"
    SUCCESS = "success"
    FAILED = "failed"


def _load_tokens() -> dict:
    try:
        if TOKENS_FILE.exists():
            return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_tokens(data: dict) -> None:
    try:
        TOKENS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not save tokens: {e}")


def _get_accounts() -> list[dict]:
    accounts = []
    for suffix in [""] + [f"_{i}" for i in range(2, 11)]:
        u = os.getenv(f"MITID_USERNAME{suffix}", "")
        i = os.getenv(f"MITID_IDENTITY{suffix}", "")
        if u:
            accounts.append({"username": u, "identity": i})
    return accounts


class AulaAuth:
    """
    Auth manager using the aula library.
    - First login: full MitID flow (QR or app notification)
    - Subsequent: automatic refresh_token renewal — no user interaction
    """

    def __init__(self, on_success):
        self.on_success = on_success
        self.state = AulaLoginState.IDLE
        self.error = None
        self.qr_image = None
        self.qr_image2 = None
        self._cancel_event = threading.Event()
        self._account_index = 0

    def get_status(self) -> dict:
        return {"state": self.state, "error": self.error, "qr_image": self.qr_image, "qr_image2": self.qr_image2}

    def start_login(self, account_index: int = 0) -> None:
        if self.state in (AulaLoginState.RUNNING, AulaLoginState.SHOW_QR):
            logger.info("Login already in progress — ignoring start_login()")
            return
        self._cancel_event.clear()
        self._account_index = account_index
        self.state = AulaLoginState.RUNNING
        self.error = None
        self.qr_image = None
        self.qr_image2 = None
        t = threading.Thread(target=self._run_in_thread, daemon=True)
        t.start()

    def cancel(self) -> None:
        self._cancel_event.set()
        self.state = AulaLoginState.IDLE
        self.error = None
        self.qr_image = None
        self.qr_image2 = None

    def _run_in_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._do_login())
        finally:
            loop.close()

    async def _do_login(self) -> None:
        try:
            from backend.aula_lib.auth.mitid_client import MitIDAuthClient
            import httpx

            accounts = _get_accounts()
            if not accounts:
                self.state = AulaLoginState.FAILED
                self.error = "MITID_USERNAME not set"
                return

            idx = self._account_index if self._account_index < len(accounts) else 0
            username = accounts[idx]["username"]
            logger.info(f"Starting MitID login for account {idx}: '{username}'")

            # Check if we have a valid refresh_token already
            token_data = _load_tokens()
            account_tokens = token_data.get(username, {})
            refresh_token = account_tokens.get("tokens", {}).get("refresh_token")

            if refresh_token:
                logger.info("Attempting token refresh before full login...")
                refreshed = await self._try_refresh(username, account_tokens)
                if refreshed:
                    # Verify using the live server client — it has current credentials
                    try:
                        from backend.main import client as live_client
                        if live_client.check_session():
                            logger.info("Token refresh verified — session is valid")
                            token_data = _load_tokens()
                            acc_tokens = token_data.get(username, {})
                            self.state = AulaLoginState.SUCCESS
                            self._notify_success(acc_tokens["tokens"], acc_tokens.get("cookies", {}))
                            return
                        else:
                            logger.warning("Token refresh OK but session check failed — proceeding with full MitID login")
                    except Exception as e:
                        logger.warning(f"Session verify error ({e}) — proceeding with full MitID login")

            # Full login flow — capture QR code for dashboard display
            def on_qr_codes(qr1, qr2) -> None:
                # Send raw QR data to frontend — JS renders it instantly without PNG lag
                try:
                    self.qr_image = qr1.get_matrix()   # list of lists of bools
                    self.qr_image2 = qr2.get_matrix()
                    self.state = AulaLoginState.SHOW_QR
                except Exception as e:
                    logger.warning(f"QR data failed: {e}")

            async with MitIDAuthClient(
                mitid_username=username,
                on_qr_codes=on_qr_codes,
                auth_method="app",  # shows QR + app notification
            ) as auth_client:
                result = await auth_client.authenticate()

            if not result.get("success"):
                raise Exception("Authentication returned no success")

            tokens = result["tokens"]
            raw_cookies = {k: v for k, v in auth_client.cookies.items()}

            # Build token_data and call create_client to run init()
            # — this sends access_token to Aula and receives PHPSESSID + Csrfp-Token
            token_data = {
                "timestamp": time.time(),
                "username": username,
                "tokens": tokens,
                "cookies": raw_cookies,
            }

            from backend.aula_lib.auth_flow import create_client
            aula_client = await create_client(token_data)
            # Extract fresh cookies after init()
            http_client = aula_client._client
            session_cookies = {k: v for k, v in http_client._client.cookies.items()}
            await aula_client.close()

            # Merge: prefer session cookies from init() over raw auth cookies
            cookies = {**raw_cookies, **session_cookies}
            token_data["cookies"] = cookies

            # Save tokens keyed by username
            all_tokens = _load_tokens()
            all_tokens[username] = token_data
            _save_tokens(all_tokens)

            logger.info(f"MitID login successful — cookies: {list(cookies.keys())}")
            self.state = AulaLoginState.SUCCESS
            self._notify_success(tokens, cookies)

        except Exception as e:
            if not self._cancel_event.is_set():
                logger.error(f"MitID login failed: {e}")
                self.state = AulaLoginState.FAILED
                self.error = str(e)

    async def _try_refresh(self, username: str, account_tokens: dict) -> bool:
        """Attempt silent token refresh. Returns True if successful."""
        try:
            from backend.aula_lib.auth_flow import _refresh_token_via_oidc
            refresh_token = account_tokens["tokens"]["refresh_token"]
            new_tokens = await _refresh_token_via_oidc(refresh_token)
            if not new_tokens or not new_tokens.get("access_token"):
                logger.info("Refresh token expired — full login required")
                return False

            # Merge new tokens, keep existing cookies
            account_tokens["tokens"].update(new_tokens)
            account_tokens["timestamp"] = time.time()

            # Re-establish Aula session cookies using new access_token
            cookies = await self._init_session_cookies(
                new_tokens["access_token"],
                account_tokens.get("cookies", {})
            )
            if cookies:
                account_tokens["cookies"] = cookies

            all_tokens = _load_tokens()
            all_tokens[username] = account_tokens
            _save_tokens(all_tokens)

            logger.info("Token refresh successful")
            return True

        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
            return False

    async def _init_session_cookies(self, access_token: str, existing_cookies: dict) -> dict | None:
        """Call Aula init endpoint with access_token to get fresh PHPSESSID + Csrfp-Token."""
        try:
            import httpx
            cookies = dict(existing_cookies)
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                r = await client.get(
                    "https://www.aula.dk/api/v23/",
                    params={
                        "method": "profiles.getProfilesByLogin",
                        "access_token": access_token,
                    },
                    cookies=cookies,
                    headers={"User-Agent": "Android"},
                )
                new_cookies = {k: v for k, v in r.cookies.items()}
                if new_cookies.get("PHPSESSID"):
                    merged = {**cookies, **new_cookies}
                    logger.info("Session cookies refreshed via access_token")
                    return merged
        except Exception as e:
            logger.warning(f"Session cookie init failed: {e}")
        return None

    def _notify_success(self, tokens: dict, cookies: dict) -> None:
        """Extract PHPSESSID + Csrfp-Token and call on_success callback."""
        phpsessid = cookies.get("PHPSESSID", "")
        csrf_token = cookies.get("Csrfp-Token", "")
        if phpsessid and csrf_token:
            self.on_success(phpsessid, csrf_token)
        else:
            logger.warning(f"Missing cookies after login — PHPSESSID={bool(phpsessid)}, Csrfp-Token={bool(csrf_token)}")


# Convenience function for background auto-refresh
async def auto_refresh_loop(auth: AulaAuth, interval_seconds: int = 50 * 60) -> None:
    """Background task: refresh tokens every 50 min (access_token lifetime is 1h)."""
    while True:
        await asyncio.sleep(interval_seconds)
        accounts = _get_accounts()
        if not accounts:
            continue
        for acc in accounts:
            username = acc["username"]
            token_data = _load_tokens()
            account_tokens = token_data.get(username, {})
            if not account_tokens.get("tokens", {}).get("refresh_token"):
                continue
            logger.info(f"Auto-refreshing token for {username}")
            success = await auth._try_refresh(username, account_tokens)
            if not success:
                logger.warning(f"Auto-refresh failed for {username} — login required")
