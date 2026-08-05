"""
backend/spotify_utils.py — Spotify OAuth helpers
Same pattern as google_utils.py
"""
import logging
import os
import time
from urllib.parse import urlencode

import requests as req

SPOTIFY_AUTH_URL  = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SCOPE     = "user-read-playback-state user-modify-playback-state user-read-currently-playing"

_spotify_token_cache: dict = {"token": "", "expires_at": 0.0}


def _client_id()     -> str: return os.getenv("SPOTIFY_CLIENT_ID", "")
def _client_secret() -> str: return os.getenv("SPOTIFY_CLIENT_SECRET", "")
def _redirect_uri() -> str:
    return os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/spotify/callback")


def get_spotify_auth_url() -> str:
    params = {
        "client_id":     _client_id(),
        "response_type": "code",
        "redirect_uri":  _redirect_uri(),
        "scope":         SPOTIFY_SCOPE,
    }
    return SPOTIFY_AUTH_URL + "?" + urlencode(params)


def get_spotify_access_token() -> str:
    cache = _spotify_token_cache
    if cache["token"] and time.time() < cache["expires_at"] - 60:
        return cache["token"]

    refresh_token = os.getenv("SPOTIFY_OAUTH_REFRESH_TOKEN", "")
    if not refresh_token:
        return ""

    try:
        r = req.post(SPOTIFY_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     _client_id(),
            "client_secret": _client_secret(),
        }, timeout=10)
        r.raise_for_status()
        tokens = r.json()
    except Exception as e:
        # Callers treat "" the same as "not connected" — without this, an
        # invalid/revoked refresh_token raises an unhandled HTTPError that
        # several call sites don't guard against (only the follow-up Spotify
        # API call is wrapped, not this token fetch).
        logging.getLogger("spotify_oauth").warning(f"Token refresh failed: {e}")
        return ""

    access_token = tokens.get("access_token", "")
    expires_in   = tokens.get("expires_in", 3600)
    os.environ["SPOTIFY_OAUTH_ACCESS_TOKEN"] = access_token
    cache["token"]      = access_token
    cache["expires_at"] = time.time() + expires_in

    # Save new refresh_token if returned
    if tokens.get("refresh_token"):
        os.environ["SPOTIFY_OAUTH_REFRESH_TOKEN"] = tokens["refresh_token"]
        _save_env("SPOTIFY_OAUTH_REFRESH_TOKEN", tokens["refresh_token"])

    logging.getLogger("spotify_oauth").info("Access token refreshed")
    return access_token


def _save_env(key: str, value: str):
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    for i, l in enumerate(lines):
        if l.startswith(f"{key}="):
            lines[i] = f"{key}={value}"; break
    else:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_spotify_connected() -> bool:
    return bool(os.getenv("SPOTIFY_OAUTH_REFRESH_TOKEN", ""))
