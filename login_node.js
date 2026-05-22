/**
 * login_node.js — MitID login for Aula via Playwright + system Chromium
 * Outputs: JSON { PHPSESSID, CSRF_TOKEN } to stdout on success
 * Usage: node login_node.js <username> [identity]
 */

// Tell playwright-core we're running on ubuntu22.04-arm64 (Android arm64)
process.env.PLAYWRIGHT_HOST_PLATFORM_OVERRIDE = 'ubuntu22.04-arm64';

const { chromium } = require('./node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const CHROMIUM_PATH = '/data/data/com.termux/files/usr/bin/chromium-browser';
const AULA_URL = 'https://www.aula.dk';
const DEBUG_DIR = path.join(__dirname, 'debug_screenshots');

const username = process.argv[2];
const identity = process.argv[3] || '';

if (!username) {
  console.error('Usage: node login_node.js <username> [identity]');
  process.exit(1);
}

async function screenshot(page, name) {
  try {
    fs.mkdirSync(DEBUG_DIR, { recursive: true });
    await page.screenshot({ path: path.join(DEBUG_DIR, `${name}.png`), fullPage: false });
  } catch (e) {}
}

async function login() {
  const browser = await chromium.launch({
    executablePath: CHROMIUM_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
    locale: 'da-DK',
  });
  const page = await context.newPage();

  // Step 1: Navigate to Aula
  await page.goto(AULA_URL, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await screenshot(page, '01_login_page');

  // Step 2: Click MitID
  await page.locator('.mit-id-logo-container').click({ timeout: 10000 });
  await page.waitForLoadState('networkidle');
  await screenshot(page, '02_unilogin');

  // Step 3: Click MitID on Unilogin selector
  await page.getByRole('button', { name: 'Mit' }).click({ timeout: 10000 });
  await page.waitForLoadState('networkidle');
  await screenshot(page, '03_mitid');

  // Step 4: Click "FORTSÆT TIL LOGIN" — wait for it to be enabled first
  const fortsaetBtn = page.getByRole('button', { name: /FORTSÆT TIL LOGIN|CONTINUE TO LOGIN/i });
  await fortsaetBtn.waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(2000); // extra wait for button to become enabled
  await fortsaetBtn.click({ timeout: 10000 });
  await page.waitForTimeout(4000); // wait for navigation, not networkidle
  await screenshot(page, '04_fortsaet');

  // Step 5: Find BRUGER-ID / username input — mirror working PC logic exactly
  await page.waitForTimeout(2000);
  const inputSelectors = [
    'input.mitid-core-user__user-id',
    'input[autocomplete="username"]',
    'input[type="text"]',
    'input[name="username"]',
  ];
  let input = null;
  for (const sel of inputSelectors) {
    try {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 })) { input = el; break; }
    } catch (e) {}
  }
  // JS fallback — find by offsetParent visibility
  if (!input) {
    const jsFound = await page.evaluate(() => {
      const inputs = document.querySelectorAll('input.mitid-core-user__user-id, input[name^="username"], input[type="text"]');
      for (const i of inputs) { if (i.offsetParent !== null) return i.name || i.id || i.className || 'found'; }
      return null;
    });
    if (jsFound && jsFound !== 'found') {
      input = page.locator(`input[name="${jsFound}"], input#${jsFound}`).first();
    } else if (jsFound) {
      input = page.locator('input[type="text"]').first();
    }
  }
  if (!input) {
    await screenshot(page, '04_no_input');
    const allInputs = await page.evaluate(() =>
      Array.from(document.querySelectorAll('input')).map(i => ({type:i.type,name:i.name,cls:i.className,visible:i.offsetParent!==null}))
    );
    throw new Error('Username input not found. Inputs: ' + JSON.stringify(allInputs));
  }

  // Focus via JS then type
  await page.evaluate(() => {
    const input = document.querySelector('input.mitid-core-user__user-id, input[name="username0"], input[type="text"]');
    if (input) { input.focus(); input.click(); }
  });
  await page.waitForTimeout(300);
  await page.keyboard.type(username, { delay: 100 });
  await screenshot(page, '05_username');
  await page.keyboard.press('Enter');

  // Output QR image to stderr as base64 for the Python wrapper to capture
  try {
    const qrBytes = await page.locator('.mitid-core-section').screenshot({ timeout: 3000 });
    process.stderr.write('QR_IMAGE_BASE64:' + qrBytes.toString('base64') + '\n');
  } catch (e) {
    const qrBytes = await page.screenshot();
    process.stderr.write('QR_IMAGE_BASE64:' + qrBytes.toString('base64') + '\n');
  }

  // Step 6: Poll for approval (3 min)
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    const url = page.url();

    // Handle loginoption page
    if (url.includes('loginoption')) {
      await screenshot(page, 'loginoption');
      const identityFirst = identity ? identity.split(' ')[0] : '';
      let clicked = false;
      for (const sel of [
        identityFirst ? `a:has-text("${identityFirst}")` : null,
        'button:has-text("privatperson")',
        '.list-group-item', 'a.list-link',
      ]) {
        if (!sel) continue;
        try {
          const el = page.locator(sel).first();
          const box = await el.boundingBox();
          if (box && box.height > 20 && box.y > 100) {
            await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
            clicked = true;
            break;
          }
        } catch (e) {}
      }
      if (!clicked) {
        const first = await page.evaluate(() => {
          const els = Array.from(document.querySelectorAll('a, button'));
          const el = els.find(e => e.offsetParent && e.getBoundingClientRect().y > 200);
          if (el) { const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }
          return null;
        });
        if (first) await page.mouse.click(first.x, first.y);
      }
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
      break;
    }

    if (url.includes('aula.dk') && !url.includes('/login') && !url.toLowerCase().includes('mitid')) break;

    // Update QR
    try {
      const qrBytes = await page.locator('.mitid-core-section').screenshot({ timeout: 2000 });
      process.stderr.write('QR_IMAGE_BASE64:' + qrBytes.toString('base64') + '\n');
    } catch (e) {}

    await page.waitForTimeout(3000);
  }

  // Wait for final redirect
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  if (!page.url().includes('aula.dk') || page.url().includes('login')) {
    await page.waitForURL(`${AULA_URL}/**`, { timeout: 30000 }).catch(() => {});
  }
  await screenshot(page, '09_final');

  // Extract cookies
  const cookies = await context.cookies();
  const phpsessid = cookies.find(c => c.name === 'PHPSESSID')?.value;
  const csrf = cookies.find(c => c.name === 'Csrfp-Token')?.value;

  await browser.close();

  if (!phpsessid || !csrf) throw new Error(`Missing cookies: ${cookies.map(c => c.name).join(', ')}`);

  // Output result as JSON to stdout
  console.log(JSON.stringify({ PHPSESSID: phpsessid, CSRF_TOKEN: csrf }));
}

login().catch(err => {
  process.stderr.write('LOGIN_ERROR:' + err.message + '\n');
  process.exit(1);
});
