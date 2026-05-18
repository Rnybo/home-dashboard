import asyncio
import base64
import logging
import os
import sys
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

sys.stdout.reconfigure(line_buffering=True)

logger = logging.getLogger("uvicorn.error")

AULA_URL = "https://www.aula.dk"
MITID_USERNAME = os.getenv("MITID_USERNAME", "")
DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_screenshots")


class AulaLoginState:
    IDLE = "idle"
    WAITING_FOR_MITID = "waiting_for_mitid"
    SHOW_QR = "show_qr"
    SUCCESS = "success"
    FAILED = "failed"


class AulaPlaywright:
    def __init__(self, on_success):
        self.on_success = on_success
        self.state = AulaLoginState.IDLE
        self.error = None
        self.qr_image = None

    def get_status(self):
        return {"state": self.state, "error": self.error, "qr_image": self.qr_image}

    def start_login(self):
        if self.state in (AulaLoginState.WAITING_FOR_MITID, AulaLoginState.SHOW_QR):
            return
        self.state = AulaLoginState.IDLE
        self.error = None
        self.qr_image = None
        import threading
        t = threading.Thread(target=self._run_in_thread, daemon=True)
        t.start()

    def _run_in_thread(self):
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._do_login())
        finally:
            loop.close()

    async def _screenshot(self, page, name):
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            path = os.path.join(DEBUG_DIR, f"{name}.png")
            await page.screenshot(path=path, full_page=False)
            logger.info(f"Screenshot: {path}")
        except Exception as e:
            logger.info(f"Screenshot failed ({name}): {e}")

    async def _do_login(self):
        self.state = AulaLoginState.WAITING_FOR_MITID
        logger.info("Starting Playwright login...")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # 1. Navigate to Aula
                await page.goto(AULA_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(1000)
                await self._screenshot(page, "01_aula")

                # 2. Click MitID on Aula login page
                await page.locator(".mit-id-logo-container").click(timeout=10000)
                await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "02_unilogin")

                # 3. Click MitID on Unilogin selector
                await page.get_by_role("button", name="Mit").click(timeout=10000)
                await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "03_nemlogin")

                # 4. Click "Continue to login" — triggers mitid/initialize POST and loads Core Client JS
                await page.wait_for_selector('#mitIDConfirmation', state='visible', timeout=15000)
                await page.click('#mitIDConfirmation')
                await self._screenshot(page, "04_confirmation")

                # 5. Wait for MitID Core Client widget, force-show it, type username, click Continue
                await page.wait_for_selector('#mitId', state='attached', timeout=30000)
                await page.evaluate("() => { const el = document.querySelector('#mitId'); if (el) el.style.display = 'block'; }")
                await page.locator('#username0').type(MITID_USERNAME, delay=50)
                await page.wait_for_timeout(300)
                await self._screenshot(page, "05_username")
                await page.locator('#loginBtn0').click(force=True)

                # 6. Show approval screen on dashboard and poll until approved (3 min)
                await page.wait_for_timeout(3000)
                await self._screenshot(page, "06_approval")
                try:
                    qr_bytes = await page.locator('#coreClientParent').screenshot(timeout=5000)
                except Exception:
                    qr_bytes = await page.screenshot()
                self.qr_image = base64.b64encode(qr_bytes).decode('utf-8')
                self.state = AulaLoginState.SHOW_QR
                logger.info("Approval screen shown on dashboard — waiting for user...")

                deadline, elapsed = 180, 0
                while elapsed < deadline:
                    if "aula.dk" in page.url and "/login" not in page.url:
                        break
                    try:
                        qr_bytes = await page.locator('#coreClientParent').screenshot(timeout=2000)
                    except Exception:
                        qr_bytes = await page.screenshot()
                    self.qr_image = base64.b64encode(qr_bytes).decode('utf-8')
                    await page.wait_for_timeout(3000)
                    elapsed += 3

                # 7. Wait for final Aula redirect
                await page.wait_for_load_state("networkidle")
                if "aula.dk" not in page.url or "login" in page.url:
                    await page.wait_for_url(f"{AULA_URL}/**", timeout=20000)
                    await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "07_success")
                logger.info(f"Final URL: {page.url}")

                # 8. Extract cookies
                cookies = await context.cookies()
                logger.info(f"Cookie names: {[c['name'] for c in cookies]}")
                phpsessid = next((c["value"] for c in cookies if c["name"] == "PHPSESSID"), None)
                csrf_token = next((c["value"] for c in cookies if c["name"] == "Csrfp-Token"), None)
                if not phpsessid or not csrf_token:
                    raise ValueError(f"Missing cookies. Got: {[c['name'] for c in cookies]}")

                await browser.close()
                self.on_success(phpsessid, csrf_token)
                self.state = AulaLoginState.SUCCESS
                logger.info("Session updated successfully!")

        except PlaywrightTimeout as e:
            self.state = AulaLoginState.FAILED
            self.error = "Timeout — MitID godkendelse tog for lang tid"
            logger.error(f"Playwright timeout: {e}")
        except Exception as e:
            self.state = AulaLoginState.FAILED
            self.error = str(e)
            logger.error(f"Playwright login failed: {e}")
