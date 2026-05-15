import asyncio
import logging
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

AULA_URL = "https://www.aula.dk"
MITID_USERNAME = os.getenv("MITID_USERNAME", "")
MITID_IDENTITY = os.getenv("MITID_IDENTITY", "")  # e.g. "Rasmus Fogh Nybo"
DEBUG = os.getenv("PLAYWRIGHT_DEBUG", "false").lower() == "true"


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
        import sys
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
        if DEBUG:
            await page.screenshot(path=f"debug_{name}.png")

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

                # Step 1: Navigate to Aula
                logger.info("Step 1: Navigating to aula.dk...")
                await page.goto(AULA_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
                await self._screenshot(page, "01_login_page")

                # Step 2: Click MitID on Aula login page
                logger.info("Step 2: Clicking MitID...")
                await page.locator(".mit-id-logo-container").click(timeout=10000)
                await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "02_unilogin_page")

                # Step 3: Click MitID on Unilogin selector
                logger.info("Step 3: Clicking MitID on Unilogin selector...")
                await page.get_by_role("button", name="Mit").click(timeout=10000)
                await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "03_mitid_page")

                # Step 4: Click Fortsæt til login
                logger.info("Step 4: Clicking Fortsæt til login...")
                await page.get_by_role("button", name="FORTSÆT TIL LOGIN").click(timeout=10000)
                await page.wait_for_timeout(2000)
                await self._screenshot(page, "04_after_fortsaet")

                # Step 5: Fill username in MitID iframe
                logger.info("Step 5: Filling username...")
                mitid_frame = page.frame(url=lambda u: "mitid" in u)
                target = mitid_frame if mitid_frame else page
                await target.wait_for_selector('.mitid-core-user__input', state='attached', timeout=15000)
                await target.evaluate('''
                    const containers = Array.from(document.querySelectorAll(".mitid-core-user__input"));
                    const visible = containers.find(el => el.offsetParent !== null);
                    if (visible) {
                        const input = visible.querySelector("input");
                        if (input) input.focus();
                    }
                ''')
                await page.keyboard.type(MITID_USERNAME, delay=50)
                await self._screenshot(page, "05_after_username")
                await page.keyboard.press('Enter')

                # Step 6: Wait for approval screen
                logger.info("Step 6: Waiting for MitID approval screen...")
                await page.wait_for_timeout(2000)
                error_text = await target.evaluate("""
                    () => {
                        const err = document.querySelector('.mitid-notification--error');
                        return err && err.offsetParent !== null ? err.innerText : null;
                    }
                """)
                if error_text:
                    raise Exception(f"MitID error: {error_text.strip()}")
                await self._screenshot(page, "06_approval_screen")

                # Step 7: Capture approval/QR screen and show on dashboard
                logger.info("Step 7: Capturing screen for dashboard...")
                import base64
                try:
                    qr_bytes = await target.locator('.mitid-core-section').screenshot(timeout=5000)
                except Exception:
                    qr_bytes = await page.screenshot(clip={'x': 150, 'y': 150, 'width': 400, 'height': 450})
                self.qr_image = base64.b64encode(qr_bytes).decode('utf-8')
                self.state = AulaLoginState.SHOW_QR
                logger.info("Approval screen shown on dashboard")

                # Step 8: Keep refreshing until approved (3 min)
                logger.info("Step 8: Waiting for approval (3 min)...")
                deadline = 180
                elapsed = 0
                while elapsed < deadline:
                    if AULA_URL in page.url and "/login" not in page.url:
                        break

                    # Check for identity selector on main page
                    try:
                        private_visible = await page.evaluate("""
                            () => {
                                const els = Array.from(document.querySelectorAll('*'));
                                return els.some(el => el.offsetParent !== null && el.textContent.includes('privatperson'));
                            }
                        """)
                        if private_visible:
                            logger.info("Identity selector found, clicking private person...")
                            # Try clicking the name row directly first
                            try:
                                await page.locator('li, div, button, a').filter(has_text="Rasmus Fogh Nybo").first.click(timeout=5000)
                                logger.info("Clicked identity by name")
                            except Exception:
                                # Fall back to clicking the privatperson heading
                                await page.get_by_text("Log på som privatperson").click(timeout=5000)
                                logger.info("Clicked privatperson heading")
                            await page.wait_for_load_state("networkidle")
                            break
                    except Exception as e:
                        logger.info(f"Identity check: {e}")

                    try:
                        qr_bytes = await target.locator('.mitid-core-section').screenshot(timeout=2000)
                    except Exception:
                        qr_bytes = await page.screenshot(clip={'x': 0, 'y': 0, 'width': 500, 'height': 500})
                    self.qr_image = base64.b64encode(qr_bytes).decode('utf-8')
                    await page.wait_for_timeout(3000)
                    elapsed += 3

                await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "09_after_approval")
                logger.info(f"Final URL: {page.url}")

                # Step 9: Extract cookies
                logger.info("Step 9: Extracting cookies...")
                cookies = await context.cookies()
                logger.info(f"Cookie names: {[c['name'] for c in cookies]}")

                phpsessid = next((c["value"] for c in cookies if c["name"] == "PHPSESSID"), None)
                csrf_token = next((c["value"] for c in cookies if c["name"] == "Csrfp-Token"), None)

                if not phpsessid or not csrf_token:
                    raise ValueError(f"Missing cookies after login. Got: {[c['name'] for c in cookies]}")

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
