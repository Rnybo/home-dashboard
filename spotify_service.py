"""
Spotify service — OAuth, token refresh, playback polling, control.
Tokens stored in spotify_tokens.json next to this file.
"""
import asyncio, json, os, time, urllib.parse, logging
from pathlib import Path
import httpx

log = logging.getLogger("spotify")

TOKEN_FILE = Path(__file__).parent / "spotify_tokens.json"
SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE  = "https://api.spotify.com/v1"


def _client_id():    return os.getenv("SPOTIFY_CLIENT_ID", "")
def _client_secret():return os.getenv("SPOTIFY_CLIENT_SECRET", "")
def _redirect_uri(): return os.getenv("SPOTIFY_REDIRECT_URI", "http://192.168.86.250:8000/api/spotify/callback")


# ── Token storage ──────────────────────────────────────────────────────────────

def load_tokens() -> dict:
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return {}

def save_tokens(data: dict):
    existing = load_tokens()
    existing.update(data)
    TOKEN_FILE.write_text(json.dumps(existing, indent=2))


# ── OAuth helpers ──────────────────────────────────────────────────────────────

def get_auth_url() -> str:
    params = {
        "client_id":     _client_id(),
        "response_type": "code",
        "redirect_uri":  _redirect_uri(),
        "scope":         SCOPE,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(TOKEN_URL, data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": _redirect_uri(),
        }, auth=(_client_id(), _client_secret()))
        r.raise_for_status()
        data = r.json()
        data["obtained_at"] = time.time()
        save_tokens(data)
        return data


async def refresh_access_token() -> str | None:
    tokens = load_tokens()
    rt = tokens.get("refresh_token")
    if not rt:
        return None
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(TOKEN_URL, data={
                "grant_type":    "refresh_token",
                "refresh_token": rt,
            }, auth=(_client_id(), _client_secret()))
            r.raise_for_status()
            data = r.json()
            data["obtained_at"] = time.time()
            if "refresh_token" not in data:
                data["refresh_token"] = rt  # keep old if not rotated
            save_tokens(data)
            return data["access_token"]
    except Exception as e:
        log.warning(f"Token refresh failed: {e}")
        return None


async def get_access_token() -> str | None:
    tokens = load_tokens()
    at = tokens.get("access_token")
    obtained = tokens.get("obtained_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    if at and time.time() < obtained + expires_in - 60:
        return at
    return await refresh_access_token()


# ── Playback API ───────────────────────────────────────────────────────────────

async def _api(method: str, path: str, **kwargs):
    token = await get_access_token()
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as c:
        r = await getattr(c, method)(
            API_BASE + path, headers=headers, timeout=6, **kwargs
        )
        if r.status_code == 401:
            token = await refresh_access_token()
            if not token:
                return None
            headers["Authorization"] = f"Bearer {token}"
            r = await getattr(c, method)(
                API_BASE + path, headers=headers, timeout=6, **kwargs
            )
        return r


async def get_current_playback() -> dict:
    r = await _api("get", "/me/player")
    if r is None or r.status_code == 204:
        return {"playing": False}
    if r.status_code != 200:
        return {"playing": False}
    data = r.json()
    item = data.get("item") or {}
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    album = item.get("album", {})
    images = album.get("images", [])
    art = images[0]["url"] if images else ""
    return {
        "playing":    data.get("is_playing", False),
        "track":      item.get("name", ""),
        "artist":     artists,
        "album":      album.get("name", ""),
        "albumArt":   art,
        "device":     data.get("device", {}).get("name", ""),
        "deviceId":   data.get("device", {}).get("id", ""),
        "progress":   data.get("progress_ms", 0),
        "duration":   item.get("duration_ms", 0),
        "trackId":    item.get("id", ""),
        "shuffleState": data.get("shuffle_state", False),
        "repeatState":  data.get("repeat_state", "off"),
    }


async def get_devices() -> list:
    r = await _api("get", "/me/player/devices")
    if r is None or r.status_code != 200:
        return []
    return r.json().get("devices", [])


async def control(action: str, device_id: str = "") -> bool:
    params = {"device_id": device_id} if device_id else {}
    endpoints = {
        "play":     ("put",  "/me/player/play"),
        "pause":    ("put",  "/me/player/pause"),
        "next":     ("post", "/me/player/next"),
        "previous": ("post", "/me/player/previous"),
    }
    if action not in endpoints:
        return False
    method, path = endpoints[action]
    r = await _api(method, path, params=params)
    return r is not None and r.status_code in (200, 204)


async def transfer_playback(device_id: str) -> bool:
    r = await _api("put", "/me/player", json={"device_ids": [device_id], "play": True})
    return r is not None and r.status_code in (200, 204)


# ── Polling engine (background asyncio task) ───────────────────────────────────

_state: dict = {"playing": False}
_subscribers: list = []  # websocket send callbacks


def get_cached_state() -> dict:
    return _state


def subscribe(callback):
    _subscribers.append(callback)

def unsubscribe(callback):
    _subscribers.discard(callback) if hasattr(_subscribers, 'discard') else (
        _subscribers.remove(callback) if callback in _subscribers else None
    )


async def _push_state(state: dict):
    dead = []
    for cb in list(_subscribers):
        try:
            await cb(state)
        except Exception:
            dead.append(cb)
    for cb in dead:
        if cb in _subscribers:
            _subscribers.remove(cb)


async def polling_loop():
    global _state
    log.info("Spotify polling started")
    while True:
        try:
            new_state = await get_current_playback()
            changed = (
                new_state.get("trackId") != _state.get("trackId") or
                new_state.get("playing") != _state.get("playing") or
                new_state.get("device")  != _state.get("device")
            )
            _state = new_state
            if changed:
                await _push_state(_state)
        except Exception as e:
            log.debug(f"Polling error: {e}")

        interval = 1.5 if _state.get("playing") else (5 if load_tokens().get("access_token") else 15)
        await asyncio.sleep(interval)
