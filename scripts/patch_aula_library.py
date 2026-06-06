"""
patch_aula_library.py — Patches the installed aula library with fixes needed for our use case.

Run after: pip install aula --ignore-requires-python

Fixes applied:
1. mitid_client.py step4: Follow POST redirect (302 Object Moved) to /loginoption manually,
   since httpx doesn't auto-follow POST redirects.
2. mitid_client.py _handle_login_option_page: Prefer privatperson over professional identity
   by matching keywords instead of always picking index 0.
"""

import sys
from pathlib import Path

# Find aula library location dynamically
try:
    import aula
    target = Path(aula.__file__).parent / "auth/mitid_client.py"
except ImportError:
    print("ERROR: aula library not installed")
    sys.exit(1)

src = target.read_text(encoding="utf-8")
original = src

# ── Fix 1: Follow POST redirect in step4 ──────────────────────────────────────
old1 = '''            response = await self._client.post(f"{MITID_BASE_URL}/login/mitid", data=params)

            if str(response.url).endswith("/loginoption"):'''

new1 = '''            response = await self._client.post(f"{MITID_BASE_URL}/login/mitid", data=params)

            # Handle 302 Object Moved — httpx doesn't auto-follow POST redirects
            location = response.headers.get("location", "")
            if response.status_code in (301, 302, 303) and location:
                _LOGGER.info(f"Step4 following redirect to: {location}")
                redirect_url = location if location.startswith("http") else f"{MITID_BASE_URL}{location}"
                response = await self._client.get(redirect_url)
            elif "Object moved" in response.text and "/loginoption" in response.text:
                _LOGGER.info("Step4 detected Object moved to /loginoption")
                response = await self._client.get(f"{MITID_BASE_URL}/loginoption")

            if str(response.url).endswith("/loginoption"):'''

# ── Fix 2: Prefer privatperson identity ───────────────────────────────────────
old2 = '''        if self._on_identity_selected:
            selected_index = await self._on_identity_selected(identities)
        else:
            _LOGGER.info("No identity selector callback; picking the first identity")
            selected_index = 0'''

new2 = '''        if self._on_identity_selected:
            selected_index = await self._on_identity_selected(identities)
        else:
            _LOGGER.info(f"Available identities: {identities}")
            # Prefer privatperson / private identity over professional
            private_keywords = ["privat", "private", "person", "borger"]
            selected_index = 0
            for i, name in enumerate(identities):
                if any(k in name.lower() for k in private_keywords):
                    selected_index = i
                    break
            _LOGGER.info(f"Auto-selected identity index {selected_index}: {identities[selected_index]}")'''

for old, new in [(old1, new1), (old2, new2)]:
    if old in src:
        src = src.replace(old, new)
        print(f"Applied patch: {old[:60].strip()!r}...")
    elif new in src:
        print(f"Already patched: {old[:60].strip()!r}...")
    else:
        print(f"ERROR - Could not find patch target: {old[:60].strip()!r}...")

if src != original:
    target.write_text(src, encoding="utf-8")
    print(f"\nPatched: {target}")
else:
    print("\nNo changes needed.")
