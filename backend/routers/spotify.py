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


@router.get("/api/spotify/search")
def spotify_search(q: str = "", type: str = "track"):
    """Søg i Spotify. type: track, album, playlist, show (podcast)."""
    token = get_spotify_access_token()
    if not token:
        raise HTTPException(401, "Spotify ikke forbundet")
    if not q.strip() or len(q.strip()) < 2:
        return {"items": []}
    allowed = {"track", "album", "playlist", "show"}
    types = ",".join(t for t in type.split(",") if t in allowed) or "track"
    try:
        r = req.get("https://api.spotify.com/v1/search",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"q": q, "type": types, "limit": 10},
                    timeout=8)
        if not r.ok:
            import logging
            logging.getLogger("spotify").error(f"Search {r.status_code}: {r.text}")
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        items = []
        for t in (data.get("tracks",    {}).get("items") or []):
            items.append({"type": "track",    "uri": t["uri"],
                          "name": t["name"],  "sub": ", ".join(a["name"] for a in t["artists"]),
                          "image": (t["album"]["images"] or [{}])[-1].get("url","")})
        for a in (data.get("albums",    {}).get("items") or []):
            items.append({"type": "album",    "uri": a["uri"],
                          "name": a["name"],  "sub": ", ".join(a2["name"] for a2 in a["artists"]),
                          "image": (a["images"] or [{}])[-1].get("url","")})
        for p in (data.get("playlists", {}).get("items") or []):
            if not p: continue
            items.append({"type": "playlist", "uri": p["uri"],
                          "name": p["name"],  "sub": p.get("owner",{}).get("display_name",""),
                          "image": ((p.get("images") or [{}])[-1] or {}).get("url","")})
        for s in (data.get("shows",     {}).get("items") or []):
            if not s: continue
            items.append({"type": "show",     "uri": s["uri"],
                          "name": s["name"],  "sub": s.get("publisher",""),
                          "image": ((s.get("images") or [{}])[-1] or {}).get("url","")})
        return {"items": items}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))


@router.post("/api/spotify/play")
async def spotify_play(request: Request):
    """Afspil en URI på en given Spotify-enhed."""
    import logging
    log = logging.getLogger("spotify")
    token = get_spotify_access_token()
    if not token:
        raise HTTPException(401, "Spotify ikke forbundet")
    body = await request.json()
    uri: str = body.get("uri", "")
    device_id: str = body.get("device_id", "")
    if not uri:
        raise HTTPException(400, "uri mangler")

    log.info(f"play uri={uri} device_id={device_id!r}")

    payload = {"uris": [uri]} if uri.startswith("spotify:track:") else {"context_uri": uri}
    params  = {"device_id": device_id} if device_id else {}
    try:
        r = req.put("https://api.spotify.com/v1/me/player/play",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params, json=payload, timeout=8)
        log.info(f"play response {r.status_code}: {r.text[:300]}")
        if r.status_code == 404 and not device_id:
            raise HTTPException(404, "no_active_device")
        if r.status_code not in (200, 204):
            raise HTTPException(r.status_code, r.text)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
