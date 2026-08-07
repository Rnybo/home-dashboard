"""
routers/settings.py — Settings GET/POST endpoints
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Request

router = APIRouter()
ROOT = Path(__file__).parent.parent.parent


@router.get("/api/first-run")
def first_run():
    """Returnerer true hvis ingen Aula-konti er konfigureret — bruges til first-run redirect."""
    return {"first_run": not bool(os.getenv("MITID_USERNAME", "").strip())}


@router.get("/api/google-oauth/calendars")
def google_oauth_calendars_public():
    """Returnerer Google-kalenderliste til settings-siden — ingen API-nøgle krævet."""
    import logging
    import requests as req
    from backend.google_utils import _get_google_access_token
    access_token = _get_google_access_token()
    if not access_token:
        return []
    try:
        items = req.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=8
        ).json().get("items", [])
        return [{"id": c.get("id"), "name": c.get("summaryOverride") or c.get("summary", c.get("id")),
                 "primary": c.get("primary", False)} for c in items]
    except Exception as ex:
        logging.warning(f"calendarList failed: {ex}")
        return []


@router.get("/api/settings")
def get_settings():
    result = {
        "api_key":                    os.getenv("API_KEY", ""),
        "anthropic_key":              "***" if os.getenv("ANTHROPIC_API_KEY") else "",
        "dashboard_title":            os.getenv("DASHBOARD_TITLE", "Hjem"),
        "accounts":                   [],
        "google_calendars":           [],
        "weather_lat":                os.getenv("WEATHER_LAT", "56.127"),
        "weather_lon":                os.getenv("WEATHER_LON", "10.178"),
        "google_client_id":           "***" if os.getenv("GOOGLE_CLIENT_ID") else "",
        "google_client_secret":       "***" if os.getenv("GOOGLE_CLIENT_SECRET") else "",
        "google_oauth_connected":     bool(os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")),
        "google_default_calendar_id": os.getenv("GOOGLE_DEFAULT_CALENDAR_ID", "primary"),
        "spotify_client_id":          "***" if os.getenv("SPOTIFY_CLIENT_ID") else "",
        "spotify_client_secret":      "***" if os.getenv("SPOTIFY_CLIENT_SECRET") else "",
        "spotify_connected":          bool(os.getenv("SPOTIFY_OAUTH_REFRESH_TOKEN")),
        "ugebrev_enabled":            os.getenv("UGEBREV_ENABLED", "") == "1",
        "ugebrev_child_id":           os.getenv("UGEBREV_CHILD_ID", ""),
    }
    for suffix in [""] + [f"_{i}" for i in range(2, 11)]:
        u = os.getenv(f"MITID_USERNAME{suffix}", "")
        i = os.getenv(f"MITID_IDENTITY{suffix}", "")
        if u or i:
            result["accounts"].append({"username": u, "identity": i})
    seen = set()
    for idx in range(1, 11):
        suffix = "" if idx == 1 else f"_{idx}"
        url  = os.getenv(f"GOOGLE_CALENDAR_ICS{suffix}", "")
        name = os.getenv(f"GOOGLE_CALENDAR_NAME{suffix}", "")
        if url and url not in seen:
            seen.add(url)
            result["google_calendars"].append({"url": url, "name": name})
    return result


@router.post("/api/settings")
async def save_settings(request: Request):
    data = await request.json()
    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    def set_env(key: str, value: str):
        nonlocal lines
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}" if value else ""
                return
        if value:
            lines.append(f"{key}={value}")

    lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]

    api_key = data.get("api_key", "").strip() or secrets.token_hex(32)
    set_env("API_KEY", api_key)

    lines = [l for l in lines if not (l.startswith("MITID_USERNAME") or l.startswith("MITID_IDENTITY"))]
    for idx, acc in enumerate(data.get("accounts", [])[:20]):
        u, i = acc.get("username", "").strip(), acc.get("identity", "").strip()
        if u or i:
            suffix = "" if idx == 0 else f"_{idx+1}"
            lines.append(f"MITID_USERNAME{suffix}={u}")
            lines.append(f"MITID_IDENTITY{suffix}={i}")

    lines = [l for l in lines if not (l.startswith("GOOGLE_CALENDAR_ICS") or l.startswith("GOOGLE_CALENDAR_NAME"))]
    new_cals = [c for c in data.get("google_calendars", [])[:20] if c.get("url", "").strip()]
    if new_cals:
        # Kun overskriv hvis der faktisk er nye kalendere — undgå at slette ved tom gem
        for idx, cal in enumerate(new_cals):
            url, name = cal.get("url", "").strip(), cal.get("name", "").strip()
            suffix = "" if idx == 0 else f"_{idx+1}"
            lines.append(f"GOOGLE_CALENDAR_ICS{suffix}={url}")
            lines.append(f"GOOGLE_CALENDAR_NAME{suffix}={name}")
    else:
        # Bevar eksisterende kalendere fra env — ingen overskrivning
        for idx in range(1, 11):
            suffix = "" if idx == 1 else f"_{idx}"
            url  = os.getenv(f"GOOGLE_CALENDAR_ICS{suffix}", "")
            name = os.getenv(f"GOOGLE_CALENDAR_NAME{suffix}", "")
            if url:
                lines.append(f"GOOGLE_CALENDAR_ICS{suffix}={url}")
                lines.append(f"GOOGLE_CALENDAR_NAME{suffix}={name}")

    gcid = data.get("google_client_id", "").strip()
    gcsc = data.get("google_client_secret", "").strip()
    if gcid and gcid != "***": set_env("GOOGLE_CLIENT_ID", gcid)
    if gcsc and gcsc != "***": set_env("GOOGLE_CLIENT_SECRET", gcsc)
    gcal = data.get("google_default_calendar_id", "").strip()
    if gcal: set_env("GOOGLE_DEFAULT_CALENDAR_ID", gcal)
    scid = data.get("spotify_client_id", "").strip()
    scsc = data.get("spotify_client_secret", "").strip()
    if scid and scid != "***": set_env("SPOTIFY_CLIENT_ID", scid)
    if scsc and scsc != "***": set_env("SPOTIFY_CLIENT_SECRET", scsc)
    if data.get("weather_lat"): set_env("WEATHER_LAT", data["weather_lat"])
    if data.get("weather_lon"): set_env("WEATHER_LON", data["weather_lon"])
    title = data.get("dashboard_title", "Hjem").strip() or "Hjem"
    set_env("DASHBOARD_TITLE", title)
    os.environ["DASHBOARD_TITLE"] = title
    ak = data.get("anthropic_key", "").strip()
    if ak and ak != "***": set_env("ANTHROPIC_API_KEY", ak)

    set_env("UGEBREV_ENABLED", "1" if data.get("ugebrev_enabled") else "")
    set_env("UGEBREV_CHILD_ID", data.get("ugebrev_child_id", "").strip())

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(override=True)

    # Update API_KEY in main module
    import backend.main as _main
    _main.API_KEY = os.getenv("API_KEY", "")

    return {"ok": True, "api_key": api_key}
