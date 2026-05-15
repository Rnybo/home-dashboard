import asyncio
import logging
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

AULA_URL = "https://www.aula.dk"
MITID_USERNAME = os.getenv("MITID_USERNAME", "")


class AulaLoginState:
    IDLE = "idle"
    WAITING_FOR_MITID = "waiting_for_mitid"
    SUCCESS = "success"
    FAILED = "failed"


class AulaPlaywright:
    def __init__(self, on_success):
        """
        on_success: async callback(phpsessid, csrf_token) called when login succeeds
        """
        self.on_success = on_success
        self.state = AulaLoginState.IDLE
        self.error = None
        self._task = None

    def get_status(self):
        return {"state": self.state, "error": self.error}

    def start_login(self):
        if self.state == AulaLoginState.WAITING_FOR_MITID:
            return  # Already in progress
        self.state = AulaLoginState.IDLE
        self.error = None
        self._task = asyncio.create_task(self._do_login())

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

                # Go to Aula
                logger.info("Navigating to aula.dk...")
                await page.goto(AULA_URL, wait_until="networkidle")

                # Click login button
                await page.click("text=Log ind", timeout=10000)
                await page.wait_for_load_state("networkidle")

                # Select MitID login option
                try:
                    await page.click("text=MitID", timeout=8000)
                    await page.wait_for_load_state("networkidle")
                except PlaywrightTimeout:
                    logger.info("No MitID button found, may already be on MitID page")

                # Fill in username (phone number or CPR)
                logger.info("Filling in MitID username...")
                await page.fill('input[autocomplete="username"], input[type="text"]', MITID_USERNAME, timeout=10000)
                await page.keyboard.press("Enter")

                # Wait for MitID app approval — user has 3 minutes to approve
                logger.info("Waiting for MitID app approval (up to 3 minutes)...")
                self.state = AulaLoginState.WAITING_FOR_MITID

                # Wait until we're back on aula.dk after successful login
                await page.wait_for_url(f"{AULA_URL}/**", timeout=180000)
                await page.wait_for_load_state("networkidle")

                logger.info("Login successful, extracting cookies...")
                cookies = await context.cookies()

                phpsessid = next((c["value"] for c in cookies if c["name"] == "PHPSESSID"), None)
                csrf_token = next((c["value"] for c in cookies if c["name"] == "Csrfp-Token"), None)

                if not phpsessid or not csrf_token:
                    raise ValueError(f"Missing cookies after login. Got: {[c['name'] for c in cookies]}")

                await browser.close()

                # Call success callback
                await self.on_success(phpsessid, csrf_token)
                self.state = AulaLoginState.SUCCESS
                logger.info("Session updated successfully via Playwright")

        except PlaywrightTimeout as e:
            self.state = AulaLoginState.FAILED
            self.error = "Timeout — MitID godkendelse tog for lang tid"
            logger.error(f"Playwright timeout: {e}")
        except Exception as e:
            self.state = AulaLoginState.FAILED
            self.error = str(e)
            logger.error(f"Playwright login failed: {e}")
