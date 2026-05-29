import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Request, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from backend.aula_client import AulaClient
from backend.mqtt_client import mqtt_client
try:
    from backend.aula_playwright import AulaPlaywright
except ModuleNotFoundError:
    from backend.aula_playwright_android import AulaPlaywright
import os
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
ROOT = Path(__file__).parent.parent  # project root (home-dashboard/)
load_dotenv(ROOT / ".env")

def _start_mdns():
    try:
        import socket
        from zeroconf import ServiceInfo, Zeroconf
        ip = socket.gethostbyname(socket.gethostname())
        info = ServiceInfo(
            "_http._tcp.local.",
            "familiekalender._http._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=8000,
            properties={"path": "/"},
            server="familiekalender.local.",
        )
        Zeroconf().register_service(info)
        logging.getLogger("mdns").info(f"mDNS: http://familiekalender.local:8000 â†’ {ip}")
    except Exception as e:
        logging.getLogger("mdns").warning(f"mDNS unavailable: {e}")

_start_mdns()

# Ensure required keys exist in .env
def _ensure_env_key(key: str, default: str):
    env_path = ROOT / ".env"
    try:
        content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        if not any(l.startswith(f"{key}=") for l in content.splitlines()):
            with open(env_path, "a", encoding="utf-8") as f:
                f.write(f"{key}={default}\n")
            os.environ[key] = default
    except Exception: pass

_ensure_env_key("DASHBOARD_TITLE", "Hjem")
_ensure_env_key("GOOGLE_CALENDAR_ICS", "")
_ensure_env_key("GOOGLE_CALENDAR_NAME", "")
_ensure_env_key("WEATHER_LAT", "")
_ensure_env_key("WEATHER_LON", "")

app = FastAPI(docs_url=None, redoc_url=None)
client = AulaClient()
def _on_login_success(phpsessid, csrf_token):
    client.update_credentials(phpsessid, csrf_token)
    mqtt_client.publish("familieoverblik/session/state", {"valid": True}, retain=True)

playwright_login = AulaPlaywright(on_success=_on_login_success)

API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    logging.warning("API_KEY is not set â€” API is unprotected!")

async def _session_keepalive():
    """Ping Aula every 6 hours to keep session alive. Publishes state via MQTT."""
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            valid = client.check_session()
            logging.getLogger("keepalive").info(f"Session keepalive: {'OK' if valid else 'EXPIRED'}")
            mqtt_client.publish("familieoverblik/session/state", {"valid": valid}, retain=True)
        except Exception as e:
            logging.getLogger("keepalive").warning(f"Keepalive failed: {e}")
            mqtt_client.publish("familieoverblik/session/state", {"valid": False}, retain=True)

async def _google_calendar_sync():
    """Every 5 minutes: sync local custom events with Google Calendar (delete, cancel, update)."""
    import asyncio, requests as req
    log = logging.getLogger("gcal_sync")
    await asyncio.sleep(60)  # wait 1 min after startup before first run
    while True:
        try:
            access_token = _get_google_access_token()
            if access_token:
                cal_id = os.getenv("GOOGLE_DEFAULT_CALENDAR_ID", "primary")
                headers = {"Authorization": f"Bearer {access_token}"}
                events = load_custom_events()
                changed = False
                for ev in events:
                    gid = ev.get("google_event_id", "")
                    if not gid:
                        continue
                    r = req.get(
                        f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events/{gid}",
                        headers=headers, timeout=8
                    )
                    if r.status_code == 404:
                        events = [e for e in events if e.get("id") != ev["id"]]
                        log.info(f"Sync: removed deleted event '{ev.get('title')}'")
                        changed = True
                        break  # list mutated â€” will re-run next cycle
                    elif r.status_code == 200:
                        g = r.json()
                        if g.get("status") == "cancelled":
                            events = [e for e in events if e.get("id") != ev["id"]]
                            log.info(f"Sync: removed cancelled event '{ev.get('title')}'")
                            changed = True
                            break
                        # Check for updates: start, end, description, title (strip child prefix)
                        import re as _re
                        g_title = _re.sub(r'^\([^)]+\)\s*-\s*', '', g.get("summary", "")).strip()
                        g_start = g.get("start", {})
                        g_end   = g.get("end", {})
                        g_start_str = g_start.get("dateTime", g_start.get("date", ""))
                        g_end_str   = g_end.get("dateTime",   g_end.get("date", ""))
                        g_desc  = g.get("description", "") or ""
                        # Normalize Google dateTime to match local format (strip seconds+tz)
                        def norm(s):
                            if not s: return ""
                            s = s[:16]  # "YYYY-MM-DDTHH:MM"
                            return s
                        g_start_norm = norm(g_start_str)
                        g_end_norm   = norm(g_end_str)
                        loc_start = norm(ev.get("start", ""))
                        loc_end   = norm(ev.get("end") or "")
                        # All-day: Google end is day-after, subtract one day
                        if "date" in g_start and "dateTime" not in g_start:
                            import datetime as _dt
                            g_start_norm = g_start.get("date", "")
                            try:
                                g_end_norm = (_dt.date.fromisoformat(g_end.get("date","")) - _dt.timedelta(days=1)).isoformat()
                            except Exception:
                                g_end_norm = g_end.get("date","")
                        updates = {}
                        if g_title and g_title != ev.get("title", ""):
                            updates["title"] = g_title
                        if g_start_norm and g_start_norm != loc_start:
                            updates["start"] = g_start_norm
                        if g_end_norm and g_end_norm != loc_end:
                            updates["end"] = g_end_norm
                        if g_desc != (ev.get("description") or ""):
                            updates["description"] = g_desc
                        if updates:
                            ev.update(updates)
                            log.info(f"Sync: updated '{ev.get('title')}' â€” {list(updates.keys())}")
                            changed = True
                if changed:
                    save_custom_events(events)
                    mqtt_client.publish("familieoverblik/events/sync", {"action": "refresh"})
        except Exception as e:
            logging.getLogger("gcal_sync").warning(f"Sync failed: {e}")
        await asyncio.sleep(300)  # 5 minutes


@app.on_event("startup")
async def startup():
    mqtt_client.connect()
    # Cast service — automatisk mDNS discovery af Google Cast/Nest enheder
    from backend.cast_service import start as cast_start
    cast_start()
    asyncio.create_task(_session_keepalive())
    asyncio.create_task(_google_calendar_sync())

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path in ("/", "/index.html"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(NoCacheMiddleware)

from backend.store import load_custom_events, save_custom_events
from backend.google_utils import (
    _get_google_access_token, _sync_google_event, _delete_google_event,
    _fmt_google_dt, GOOGLE_TOKEN_URL, GOOGLE_AUTH_URL, GOOGLE_OAUTH_SCOPES,
    _google_token_cache,
)


def check_api_key(request: Request):
    if API_KEY and request.headers.get("x-api-key", "") != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

# ── Routers ───────────────────────────────────────────────────────────────────
from backend.routers import custom as custom_router
from backend.routers import weather as weather_router
from backend.routers import google as google_router
from backend.routers import aula as aula_router
from backend.routers import settings as settings_router
from backend.routers import spotify as spotify_router
from backend.routers.cast import router as cast_router, router_auth as cast_router_auth
app.include_router(custom_router.router)
app.include_router(weather_router.router, dependencies=[Depends(check_api_key)])
app.include_router(google_router.router, dependencies=[Depends(check_api_key)])
app.include_router(aula_router.router, dependencies=[Depends(check_api_key)])
app.include_router(settings_router.router)
app.include_router(spotify_router.router)
app.include_router(cast_router)
app.include_router(cast_router_auth, dependencies=[Depends(check_api_key)])  # ingen auth — settings bruges fra settings.html uden API-nøgle


def aula_call(fn):
    try:
        return fn()
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
def config(request: Request):
    referer = request.headers.get("referer", "")
    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")
    if referer and host and host not in referer and host not in origin:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"api_key": API_KEY, "dashboard_title": os.getenv("DASHBOARD_TITLE", "Hjem")}


@app.get("/api/status", dependencies=[Depends(check_api_key)])
def status():
    return {"session_valid": client.check_session()}


@app.get("/api/file-proxy", dependencies=[Depends(check_api_key)])
def file_proxy(url: str):
    """Proxy an Aula file URL through the authenticated session so all devices can access it."""
    import urllib.parse
    if not url:
        raise HTTPException(400, "url required")
    # Only allow aula.dk URLs for security
    parsed = urllib.parse.urlparse(url)
    allowed = parsed.netloc.endswith("aula.dk") or parsed.netloc.endswith("aula-prod.aula.dk")
    if not allowed:
        raise HTTPException(403, "Only aula.dk URLs are allowed")
    try:
        r = client.session.get(url, stream=True, timeout=30)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "application/octet-stream")
        content_disp = r.headers.get("Content-Disposition", "")
        # For PDFs serve inline, everything else as attachment
        if "pdf" in content_type:
            disp = "inline"
        elif content_disp:
            disp = content_disp
        else:
            filename = url.split("/")[-1].split("?")[0] or "file"
            disp = f'attachment; filename="{filename}"'
        headers = {"Content-Disposition": disp}
        if "Content-Length" in r.headers:
            headers["Content-Length"] = r.headers["Content-Length"]
        return StreamingResponse(r.iter_content(chunk_size=65536), media_type=content_type, headers=headers)
    except Exception as e:
        raise HTTPException(502, f"Could not fetch file: {e}")




@app.get("/api/profile-picture")
def profile_picture(url: str):
    import urllib.parse
    if not url:
        raise HTTPException(400, "url required")
    parsed = urllib.parse.urlparse(url)
    if not (parsed.netloc.endswith("aula.dk") or "media-prod.aula.dk" in parsed.netloc):
        raise HTTPException(403, "Only aula.dk URLs are allowed")
    try:
        # Try direct fetch first (works for signed URLs)
        r = client.session.get(url, timeout=10)
        if r.status_code == 403:
            # Unsigned URL — try to get signed version via Aula file-proxy API
            signed = client.session.get(
                f"https://www.aula.dk/api/v23/?method=mediaFiles.getSignedUrls",
                params={"urls[]": url}, timeout=8
            )
            if signed.ok:
                data = signed.json().get("data", {})
                signed_url = (data.get("signedUrls") or {}).get(url, "")
                if signed_url:
                    r = client.session.get(signed_url, timeout=10)
        r.raise_for_status()
        from fastapi.responses import Response
        return Response(content=r.content,
                        media_type=r.headers.get("Content-Type", "image/jpeg"),
                        headers={"Cache-Control": "max-age=3600"})
    except Exception as e:
        raise HTTPException(502, str(e))


app.mount("/", StaticFiles(directory=str(Path(__file__).parent.parent / "frontend"), html=True), name="static")
