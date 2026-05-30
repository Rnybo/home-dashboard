"""
routers/spotify.py — Spotify OAuth endpoints
"""
import os
from pathlib import Path

import requests as req
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from backend.spotify_utils import (
    get_spotify_auth_url, get_spotify_access_token,
    is_spotify_connected, SPOTIFY_TOKEN_URL, _client_id, _client_secret, _redirect_uri,
)

router = APIRouter()
ROOT = Path(__file__).parent.parent.parent


@router.get("/api/spotify-oauth/connect")
def spotify_connect():
    if not _client_id():
        raise HTTPException(400, "SPOTIFY_CLIENT_ID not configured")
    return {"auth_url": get_spotify_auth_url()}


@router.get("/auth/spotify/callback")
def spotify_callback(code: str = "", error: str = ""):
    if error:
        return RedirectResponse(url=f"/settings.html?spotify=error&reason={error}")
    if not code:
        raise HTTPException(400, "No code received")

    r = req.post(SPOTIFY_TOKEN_URL, data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  _redirect_uri(),
        "client_id":     _client_id(),
        "client_secret": _client_secret(),
    }, timeout=10)
    r.raise_for_status()
    tokens = r.json()

    refresh_token = tokens.get("refresh_token", "")
    access_token  = tokens.get("access_token", "")

    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    def set_env(key, val):
        nonlocal lines
        for i, l in enumerate(lines):
            if l.startswith(f"{key}="):
                lines[i] = f"{key}={val}"; return
        lines.append(f"{key}={val}")

    if refresh_token: set_env("SPOTIFY_OAUTH_REFRESH_TOKEN", refresh_token)
    set_env("SPOTIFY_OAUTH_ACCESS_TOKEN", access_token)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(env_path, override=True)

    return RedirectResponse(url="/settings.html?spotify=success")


@router.get("/api/spotify-oauth/status")
def spotify_status():
    connected = is_spotify_connected()
    return {"connected": connected}


@router.get("/api/spotify/devices")
def spotify_devices():
    """Returnerer Spotify-enheder — bruges til at matche Cast-enhedsnavne."""
    token = get_spotify_access_token()
    if not token:
        return {"devices": []}
    try:
        r = req.get("https://api.spotify.com/v1/me/player/devices",
                    headers={"Authorization": f"Bearer {token}"}, timeout=8)
        r.raise_for_status()
        return {"devices": r.json().get("devices", [])}
    except Exception:
        return {"devices": []}
