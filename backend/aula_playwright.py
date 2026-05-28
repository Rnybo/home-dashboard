import asyncio
import base64
import logging
import os
import sys
import threading
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

sys.stdout.reconfigure(line_buffering=True)

logger = logging.getLogger("uvicorn.error")

AULA_URL = "https://www.aula.dk"
DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_screenshots")


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
        self._cancel_event = threading.Event()

    def get_status(self):
        return {"state": self.state, "error": self.error, "qr_image": self.qr_image}

    def start_login(self, account_index: int = 0):
        if self.state in (AulaLoginState.RUNNING, AulaLoginState.SHOW_QR):
            logger.info("Login already in progress — ignoring start_login()")
            return
        self._cancel_event.clear()
        self.state = AulaLoginState.RUNNING
        self.error = None
        self.qr_image = None
        self._account_index = account_index
        t = threading.Thread(target=self._run_in_thread, daemon=True)
        t.start()

    def cancel(self):
        self._cancel_event.set()
        self.state = AulaLoginState.IDLE
        self.error = None
        self.qr_image = None

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
        # Build list of accounts from env — supports MITID_USERNAME, MITID_USERNAME_2, etc.
        accounts = []
        for suffix in ["", "_2", "_3", "_4", "_5"]:
            u = os.getenv(f"MITID_USERNAME{suffix}", "")
            i = os.getenv(f"MITID_IDENTITY{suffix}", "")
            if u:
                accounts.append({"username": u, "identity": i})
        if not accounts:
            self.state = AulaLoginState.FAILED
            self.error = "MITID_USERNAME not set"
            return
        idx = getattr(self, '_account_index', 0)
        if idx >= len(accounts):
            idx = 0
        mitid_username = accounts[idx]["username"]
        mitid_identity = accounts[idx]["identity"]
        logger.info(f"Starting Playwright login with account {idx}: '{mitid_username}'")
        try:
            async with async_playwright() as p:
                # Find Chromium executable — prefer system Chromium on Android/Termux
                chromium_paths = [
                    os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"),
                    "/data/data/com.termux/files/usr/bin/chromium-browser",
                    "/data/data/com.termux/files/usr/bin/chromium",
                    "/usr/bin/chromium-browser",
                    "/usr/bin/chromium",
                ]
                executable_path = None
                for path in chromium_paths:
                    if path and os.path.exists(path):
                        logger.info(f"Using system Chromium: {path}")
                        executable_path = path
                        break

                launch_kwargs = dict(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
                )
                if executable_path:
                    launch_kwargs["executable_path"] = executable_path

                browser = await p.chromium.launch(**launch_kwargs)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 900}
                )
                page = await context.new_page()

                # Step 1: Navigate to Aula
                await page.goto(AULA_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                await self._screenshot(page, "01_login_page")

                # Step 2: Click MitID on Aula login page
                await page.locator(".mit-id-logo-container").click(timeout=10000)
                await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "02_unilogin_page")

                # Step 3: Click MitID on Unilogin selector
                await page.get_by_role("button", name="Mit").click(timeout=10000)
                await page.wait_for_load_state("networkidle")
                await self._screenshot(page, "03_mitid_page")

                # Step 4: Click Fortsæt til login
                await page.get_by_role("button", name="FORTSÆT TIL LOGIN").click(timeout=10000)
                await page.wait_for_timeout(4000)
                await self._screenshot(page, "04_after_fortsaet")

                # Step 5: Find and fill username
                await page.wait_for_timeout(2000)
                logger.info(f"Frames: {[f.url for f in page.frames]}")

                selectors = [
                    'input.mitid-core-user__user-id',
                    'input[autocomplete="username"]',
                    'input[type="text"]',
                    'input[name="username"]',
                ]

                username_input = None
                for sel in selectors:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=1500):
                            username_input = el
                            logger.info(f"Found input (visible): {sel}")
                            break
                    except Exception:
                        pass

                # Fallback: use JS visibility (offsetParent) instead of Playwright is_visible
                if not username_input:
                    js_visible = await page.evaluate("""() => {
                        const inputs = document.querySelectorAll('input.mitid-core-user__user-id, input[name^="username"]');
                        for (const i of inputs) { if (i.offsetParent !== null) return i.name || i.id || 'found'; }
                        return null;
                    }""")
                    logger.info(f"JS visible input: {js_visible}")
                    if js_visible:
                        username_input = page.locator(f'input[name="{js_visible}"]').first
                        logger.info(f"Using JS-found input: {js_visible}")

                if not username_input:
                    await self._screenshot(page, "05_no_input_found")
                    all_inputs = await page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(i => ({type:i.type,name:i.name,cls:i.className,visible:i.offsetParent!==null}))""")
                    logger.info(f"All inputs: {all_inputs}")
                    raise Exception(f"Could not find username input")

                await page.evaluate("""() => {
                    const input = document.querySelector('input.mitid-core-user__user-id, input[name="username0"]');
                    if (input) { input.focus(); input.click(); }
                }""")
                await page.wait_for_timeout(300)
                await page.keyboard.type(mitid_username, delay=100)
                await self._screenshot(page, "05_after_username")
                await page.keyboard.press('Enter')

                # Step 6: Wait for approval screen
                await page.wait_for_timeout(5000)
                await self._screenshot(page, "06_approval_screen")

                try:
                    qr_bytes = await page.locator('.mitid-core-section').screenshot(timeout=5000)
                except Exception:
                    qr_bytes = await page.screenshot()
                self.qr_image = base64.b64encode(qr_bytes).decode('utf-8')
                self.state = AulaLoginState.SHOW_QR
                logger.info("Approval screen shown on dashboard")

                # Step 7: Poll until approved (3 min)
                deadline, elapsed = 180, 0
                while elapsed < deadline:
                    if self._cancel_event.is_set():
                        return
                    if "aula.dk" in page.url and "/login" not in page.url and "mitid" not in page.url.lower():
                        break

                    # Always update qr_image so frontend shows current screen state
                    try:
                        section = page.locator('.mitid-core-section')
                        if await section.count() > 0:
                            qr_bytes = await section.screenshot(timeout=2000)
                        else:
                            qr_bytes = await page.screenshot()
                        self.qr_image = base64.b64encode(qr_bytes).decode('utf-8')
                        self.state = AulaLoginState.SHOW_QR
                    except Exception:
                        pass

                    # Handle loginoption page — click private person identity
                    if "loginoption" in page.url:
                        logger.info("loginoption detected, clicking private identity...")
                        await self._screenshot(page, "loginoption")
                        clicked = False
                        # Try to match by identity name from env, fall back to first private option
                        identity_name = mitid_identity.split()[0] if mitid_identity else ""
                        for sel in [
                            f'a:has-text("{identity_name}")' if identity_name else None,
                            'button:has-text("privatperson")',
                            '.list-group-item', 'a.list-link', 'li a', 'li button',
                        ]:
                            try:
                                if not sel:
                                    continue
                                el = page.locator(sel).first
                                box = await el.bounding_box()
                                if box and box['height'] > 20 and box['y'] > 100:
                                    await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                    logger.info(f"Mouse-clicked loginoption '{sel}' at y={box['y']:.0f}")
                                    clicked = True
                                    break
                            except Exception:
                                pass
                        if not clicked:
                            # Fallback: first visible link/button below y=200
                            first = await page.evaluate("""() => {
                                const els = Array.from(document.querySelectorAll('a, button'));
                                const el = els.find(e => e.offsetParent && e.getBoundingClientRect().y > 200);
                                if (el) { const r = el.getBoundingClientRect(); return {x: r.x+r.width/2, y: r.y+r.height/2}; }
                                return null;
                            }""")
                            if first:
                                await page.mouse.click(first['x'], first['y'])
                                logger.info(f"loginoption fallback click at {first}")
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        logger.info(f"URL after loginoption: {page.url}")
                        break

                    await page.wait_for_timeout(3000)
                    elapsed += 3

                # Step 8: Final redirect and cookies
                # After loginoption click, wait for navigation then check URL
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                logger.info(f"URL after loginoption: {page.url}")

                if "aula.dk" not in page.url or "login" in page.url:
                    try:
                        await page.wait_for_url(f"{AULA_URL}/**", timeout=30000)
                    except PlaywrightTimeout:
                        logger.warning(f"wait_for_url timeout, current URL: {page.url}")
                    await page.wait_for_load_state("networkidle", timeout=10000)
                await self._screenshot(page, "09_after_approval")
                logger.info(f"Final URL: {page.url}")

                phpsessid, csrf_token = None, None
                for attempt in range(5):
                    cookies = await context.cookies()
                    phpsessid = next((c["value"] for c in cookies if c["name"] == "PHPSESSID"), None)
                    csrf_token = next((c["value"] for c in cookies if c["name"] == "Csrfp-Token"), None)
                    if phpsessid and csrf_token:
                        break
                    logger.info(f"Cookie attempt {attempt+1}/5: {[c['name'] for c in cookies]}")
                    await page.wait_for_timeout(2000)

                if not phpsessid or not csrf_token:
                    raise ValueError(f"Missing cookies: {[c['name'] for c in await context.cookies()]}")

                await browser.close()
                self.on_success(phpsessid, csrf_token)
                self.state = AulaLoginState.SUCCESS
                self.qr_image = None
                logger.info("Session updated successfully!")

        except PlaywrightTimeout as e:
            if not self._cancel_event.is_set():
                self.state = AulaLoginState.FAILED
                self.error = "Timeout — MitID godkendelse tog for lang tid"
                logger.error(f"Playwright timeout: {e}")
        except Exception as e:
            if not self._cancel_event.is_set():
                self.state = AulaLoginState.FAILED
                self.error = str(e)
                logger.error(f"Playwright login failed: {e}", exc_info=True)
