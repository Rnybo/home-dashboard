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
        logging.getLogger("mdns").info(f"mDNS: http://familiekalender.local:8000 → {ip}")
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
    logging.warning("API_KEY is not set — API is unprotected!")

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
                        break  # list mutated — will re-run next cycle
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
                            log.info(f"Sync: updated '{ev.get('title')}' — {list(updates.keys())}")
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


@app.get("/")
async def index():
    resp = FileResponse(Path(__file__).parent.parent / "frontend" / "index.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


def check_api_key(request: Request):
    if API_KEY and request.headers.get("x-api-key", "") != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


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


@app.get("/api/login/accounts", dependencies=[Depends(check_api_key)])
def login_accounts():
    accounts = []
    for suffix in [""] + [f"_{i}" for i in range(2, 11)]:
        identity = os.getenv(f"MITID_IDENTITY{suffix}", "")
        username = os.getenv(f"MITID_USERNAME{suffix}", "")
        if username:
            name = identity.split()[0] if identity else username
            accounts.append({"index": len(accounts), "name": name})
    return accounts


@app.post("/api/login/start", dependencies=[Depends(check_api_key)])
async def login_start(account_index: int = 0):
    playwright_login.start_login(account_index=account_index)
    return {"ok": True}


@app.get("/api/login/status", dependencies=[Depends(check_api_key)])
def login_status():
    return playwright_login.get_status()


@app.post("/api/login/cancel", dependencies=[Depends(check_api_key)])
async def login_cancel():
    playwright_login.cancel()
    return {"ok": True}


@app.get("/api/profile-config", dependencies=[Depends(check_api_key)])
def profile_config():
    def fn():
        data = client.get_profile().get("data", {})
        institutions = data.get("institutions") or []
        children, inst_profile_ids = [], []
        for inst in institutions:
            inst_profile_ids.append(inst.get("institutionProfileId"))
            for child in inst.get("children") or []:
                children.append({
                    "id": child.get("id"),
                    "name": child.get("name", "").split()[0],  # first name
                    "photoUrl": child.get("profilePicture", {}).get("url", ""),
                })
        return {"children": children, "inst_profile_ids": [i for i in inst_profile_ids if i]}
    return aula_call(fn)


@app.get("/api/profile", dependencies=[Depends(check_api_key)])
def profile():
    return aula_call(client.get_profile)


@app.get("/api/messages", dependencies=[Depends(check_api_key)])
def messages(page: int = 0):
    def fn():
        threads = client.get_threads(page)
        return [{"id": t["id"], "subject": t.get("subject", ""), "read": t.get("read", True)} for t in threads]
    return aula_call(fn)


@app.get("/api/messages/{thread_id}", dependencies=[Depends(check_api_key)])
def thread(thread_id: int):
    return aula_call(lambda: client.get_messages_for_thread(thread_id))


@app.get("/api/presence", dependencies=[Depends(check_api_key)])
def presence(inst_profile_ids: str = "", from_date: str = "", to_date: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_presence(ids, from_date or None, to_date or None))


@app.get("/api/calendar", dependencies=[Depends(check_api_key)])
def calendar(inst_profile_ids: str = "", from_date: str = "", to_date: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_calendar_events(ids, from_date or None, to_date or None))


@app.get("/api/posts", dependencies=[Depends(check_api_key)])
def posts(inst_profile_ids: str = "", index: int = 0):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_posts(ids, index))


@app.get("/api/important-dates", dependencies=[Depends(check_api_key)])
def important_dates(inst_profile_ids: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_important_dates(ids))


@app.get("/api/birthdays", dependencies=[Depends(check_api_key)])
def birthdays(inst_profile_ids: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_birthdays(ids))


@app.get("/api/google-calendar", dependencies=[Depends(check_api_key)])
def google_calendar(from_date: str = "", to_date: str = ""):
    import datetime, requests as req
    from icalendar import Calendar
    import recurring_ical_events

    colors = ["#e53935","#8e24aa","#1e88e5","#43a047","#fb8c00"]
    today     = datetime.date.today()
    date_from = datetime.date.fromisoformat(from_date) if from_date else today
    date_to   = datetime.date.fromisoformat(to_date)   if to_date   else today + datetime.timedelta(days=6)

    events = []

    # ── OAuth path: fetch calendars via Google Calendar API ──────────────────
    access_token = _get_google_access_token()
    if access_token:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            # List all calendars for the user
            cal_list = req.get(
                "https://www.googleapis.com/calendar/v3/users/me/calendarList",
                headers=headers, timeout=8
            ).json().get("items", [])

            color_map = {
                "tomato":"#e53935","flamingo":"#f06292","tangerine":"#fb8c00",
                "banana":"#f9a825","sage":"#81c784","basil":"#43a047",
                "peacock":"#1e88e5","blueberry":"#3949ab","lavender":"#9575cd",
                "grape":"#8e24aa","graphite":"#757575",
            }

            for idx, cal in enumerate(cal_list):
                cal_id    = cal.get("id", "")
                cal_name  = cal.get("summaryOverride") or cal.get("summary", cal_id)
                bg_color  = cal.get("backgroundColor", "")
                color_id  = cal.get("colorId", "")
                color     = bg_color or color_map.get(color_id, colors[min(idx, len(colors)-1)])

                try:
                    resp = req.get(
                        f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events",
                        headers=headers,
                        params={
                            "timeMin":      f"{date_from.isoformat()}T00:00:00Z",
                            "timeMax":      f"{date_to.isoformat()}T23:59:59Z",
                            "singleEvents": "true",
                            "orderBy":      "startTime",
                            "maxResults":   100,
                        },
                        timeout=8
                    )
                    resp.raise_for_status()
                    for item in resp.json().get("items", []):
                        start = item.get("start", {})
                        end   = item.get("end",   {})
                        all_day = "date" in start and "dateTime" not in start
                        ext_cals = item.get("extendedProperties", {}).get("private", {}).get("familieoverblik_calendars", "")
                        events.append({
                            "title":    item.get("summary", "(ingen titel)"),
                            "start":    start.get("dateTime") or start.get("date", ""),
                            "end":      end.get("dateTime")   or end.get("date", ""),
                            "allDay":   all_day,
                            "owner":    cal_name,
                            "color":    color,
                            "location": item.get("location", ""),
                            "familieoverblik_calendars": ext_cals,
                        })
                except Exception as ex:
                    logging.warning(f"Google Calendar API fetch failed for {cal_name}: {ex}")

        except Exception as ex:
            logging.warning(f"Google Calendar API calendarList failed: {ex}")
            access_token = ""  # fall through to ICS

    # ── ICS fallback (no OAuth or OAuth failed) ───────────────────────────────
    if not access_token:
        seen, ics_calendars = set(), []
        for idx in range(1, 11):
            suffix = "" if idx == 1 else f"_{idx}"
            url  = os.getenv(f"GOOGLE_CALENDAR_ICS{suffix}", "")
            name = os.getenv(f"GOOGLE_CALENDAR_NAME{suffix}", f"Kalender {idx}")
            if url and url not in seen:
                seen.add(url); ics_calendars.append({"url": url, "name": name, "color": colors[min(idx-1, len(colors)-1)]})
        ics_calendars.append({"url": "https://calendar.google.com/calendar/ical/da.danish%23holiday%40group.v.calendar.google.com/public/basic.ics", "name": "Helligdag", "color": "#f59e0b"})

        for cal in ics_calendars:
            if not cal["url"]: continue
            try:
                r = req.get(cal["url"], timeout=8)
                r.raise_for_status()
                gcal = Calendar.from_ical(r.content)
                for component in recurring_ical_events.of(gcal).between(date_from, date_to):
                    if component.name != "VEVENT": continue
                    dtstart = component.get("DTSTART")
                    dtend   = component.get("DTEND")
                    if not dtstart: continue
                    val = dtstart.dt
                    all_day = not hasattr(val, "hour")
                    start_iso = val.isoformat() if all_day else val.astimezone().isoformat()
                    end_val   = dtend.dt if dtend else val
                    end_iso   = end_val.isoformat() if all_day else (end_val.astimezone().isoformat() if hasattr(end_val, "hour") else end_val.isoformat())
                    events.append({
                        "title":    str(component.get("SUMMARY", "(ingen titel)")),
                        "start":    start_iso,
                        "end":      end_iso,
                        "allDay":   all_day,
                        "owner":    cal["name"],
                        "color":    cal["color"],
                        "location": str(component.get("LOCATION", "")),
                    })
            except Exception as ex:
                logging.warning(f"ICS fetch failed for {cal['name']}: {ex}")

    # Always add helligdage via ICS (not in personal calendar list)
    if access_token:
        try:
            r = req.get("https://calendar.google.com/calendar/ical/da.danish%23holiday%40group.v.calendar.google.com/public/basic.ics", timeout=8)
            r.raise_for_status()
            gcal = Calendar.from_ical(r.content)
            for component in recurring_ical_events.of(gcal).between(date_from, date_to):
                if component.name != "VEVENT": continue
                dtstart = component.get("DTSTART")
                if not dtstart: continue
                val = dtstart.dt
                all_day = not hasattr(val, "hour")
                dtend = component.get("DTEND")
                end_val = dtend.dt if dtend else val
                events.append({
                    "title":    str(component.get("SUMMARY", "")),
                    "start":    val.isoformat(),
                    "end":      end_val.isoformat(),
                    "allDay":   all_day,
                    "owner":    "Helligdag",
                    "color":    "#f59e0b",
                    "location": "",
                })
        except Exception as ex:
            logging.warning(f"Helligdage ICS failed: {ex}")

    return events


@app.get("/api/routes", dependencies=[Depends(check_api_key)])
def routes():
    import requests as req
    api_key = os.getenv("ORS_API_KEY", "")
    if not api_key or api_key == "din-api-nøgle-her":
        raise HTTPException(status_code=503, detail="ORS_API_KEY not configured")
    origin_lat = float(os.getenv("ORS_ORIGIN_LAT", "56.1147"))
    origin_lon = float(os.getenv("ORS_ORIGIN_LON", "10.2089"))
    destinations = []
    for i in range(1, 6):
        name = os.getenv(f"ORS_DEST_{i}_NAME", "")
        if not name: break
        destinations.append({
            "name": name,
            "lat": float(os.getenv(f"ORS_DEST_{i}_LAT", "0")),
            "lon": float(os.getenv(f"ORS_DEST_{i}_LON", "0")),
            "default": os.getenv(f"ORS_DEST_{i}_DEFAULT", "cycling-regular"),
        })
    profiles = ["cycling-regular", "foot-walking", "driving-car"]
    profile_labels = {"cycling-regular": "🚴", "foot-walking": "🚶", "driving-car": "🚗"}
    result = []
    for dest in destinations:
        dest_result = {"name": dest["name"], "default": dest["default"], "modes": {}}
        for profile in profiles:
            try:
                r = req.post(
                    f"https://api.openrouteservice.org/v2/directions/{profile}",
                    headers={"Authorization": api_key, "Content-Type": "application/json"},
                    json={"coordinates": [[origin_lon, origin_lat], [dest["lon"], dest["lat"]]]},
                    timeout=6
                )
                r.raise_for_status()
                seg = r.json()["routes"][0]["summary"]
                dest_result["modes"][profile] = {
                    "label": profile_labels[profile],
                    "duration": int(seg["duration"] / 60),  # minutes
                    "distance": round(seg["distance"] / 1000, 1),  # km
                }
            except Exception as ex:
                logging.warning(f"ORS {profile} to {dest['name']}: {ex}")
        result.append(dest_result)
    return result



@app.get("/api/weather", dependencies=[Depends(check_api_key)])
def weather():
    import requests as req, datetime
    lat = os.getenv("WEATHER_LAT", "56.127")
    lon = os.getenv("WEATHER_LON", "10.178")
    try:
        r = req.get(
            f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}",
            headers={"User-Agent": "home-dashboard/1.0 github.com/Rnybo/home-dashboard"},
            timeout=8
        )
        r.raise_for_status()
        series = r.json()["properties"]["timeseries"]
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        result = []
        seen_hours = set()
        for entry in series:
            t = datetime.datetime.fromisoformat(entry["time"])
            hour = t.replace(minute=0, second=0, microsecond=0)
            if hour < now - datetime.timedelta(minutes=30): continue
            if hour in seen_hours: continue
            seen_hours.add(hour)
            instant = entry["data"]["instant"]["details"]
            next1h = entry["data"].get("next_1_hours", {})
            next6h = entry["data"].get("next_6_hours", {})
            result.append({
                "time": hour.isoformat(),
                "temp": round(instant.get("air_temperature", 0)),
                "wind": round(instant.get("wind_speed", 0), 1),
                "wind_dir": round(instant.get("wind_from_direction", 0)),
                "symbol": next1h.get("summary", {}).get("symbol_code", "")
                          or next6h.get("summary", {}).get("symbol_code", ""),
                "precip": next1h.get("details", {}).get("precipitation_amount", 0)
                          or next6h.get("details", {}).get("precipitation_amount", 0),
            })
            if len(result) >= 168: break  # 7 days × 24h
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/gallery/albums", dependencies=[Depends(check_api_key)])
def gallery_albums(inst_profile_ids: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_albums(ids))


@app.get("/api/gallery/albums/{album_id}/media", dependencies=[Depends(check_api_key)])
def gallery_album_media(album_id: int, inst_profile_ids: str = "", index: int = 0):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_album_media(album_id, ids, index))


@app.get("/api/gallery/user-media", dependencies=[Depends(check_api_key)])
def gallery_user_media(inst_profile_ids: str = "", index: int = 0, limit: int = 12):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: client.get_user_media(ids, index, limit))


@app.get("/api/groups", dependencies=[Depends(check_api_key)])
def groups():
    return aula_call(client.get_groups_cached)


@app.get("/api/groups/{group_id}/contacts", dependencies=[Depends(check_api_key)])
def group_contacts(group_id: int):
    return aula_call(lambda: client.get_contact_list(group_id))


@app.get("/api/profile-picture")
def profile_picture(url: str):
    """Proxy a signed Aula profile picture URL through the authenticated session."""
    import urllib.parse
    if not url:
        raise HTTPException(400, "url required")
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("aula.dk") and not parsed.netloc.endswith("aula-prod.aula.dk") and "media-prod.aula.dk" not in parsed.netloc:
        raise HTTPException(403, "Only aula.dk URLs are allowed")
    try:
        content_type, data = client.get_profile_picture_url(url)
        if not data:
            raise HTTPException(404, "No picture")
        from fastapi.responses import Response
        return Response(content=data, media_type=content_type,
                       headers={"Cache-Control": "max-age=3600"})
    except Exception as e:
        raise HTTPException(502, str(e))


@app.post("/api/logout")
def logout():
    import json
    p = ROOT / "session.json"
    if p.exists():
        p.write_text(json.dumps({}))
    client.update_credentials({})
    return {"ok": True}


# ── Custom events ─────────────────────────────────────────────────────────────

CUSTOM_EVENTS_FILE = ROOT / "custom_events.json"

def load_custom_events() -> list:
    with _custom_events_lock:
        try:    return json.loads(CUSTOM_EVENTS_FILE.read_text(encoding="utf-8"))
        except: return []

def save_custom_events(events: list):
    with _custom_events_lock:
        CUSTOM_EVENTS_FILE.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/custom-events")
def get_custom_events():
    return load_custom_events()

@app.post("/api/custom-events")
async def add_custom_event(request: Request):
    import uuid, threading
    data = await request.json()
    event = {
        "id":          str(uuid.uuid4()),
        "title":       data.get("title", "").strip(),
        "start":       data.get("start", ""),
        "end":         data.get("end") or None,
        "allDay":      data.get("allDay", False),
        "description": data.get("description", ""),
        "color":       data.get("color", "#7c3aed"),
        "calendar":    data.get("calendar", ""),
        "google_event_id": "",
    }
    events = load_custom_events()
    events.append(event)
    save_custom_events(events)

    # Sync to Google Calendar in background — don't block the response
    def _bg_sync():
        gid = _sync_google_event(event)
        if gid:
            all_ev = load_custom_events()
            for e in all_ev:
                if e.get("id") == event["id"]:
                    e["google_event_id"] = gid
                    break
            save_custom_events(all_ev)

    threading.Thread(target=_bg_sync, daemon=True).start()
    return {"ok": True, "id": event["id"]}


@app.delete("/api/custom-events/{event_id}")
def delete_custom_event(event_id: str, calendar: str = ""):
    """Delete event. If calendar given, only remove that tag — delete Google event when no calendars left."""
    import threading
    all_events = load_custom_events()
    target = next((e for e in all_events if e.get("id") == event_id), None)

    if target and calendar:
        current_cals = [c.strip() for c in target.get("calendar", "").split(",") if c.strip()]
        current_cals = [c for c in current_cals if c != calendar]

        if current_cals:
            target["calendar"] = ",".join(current_cals)
            # Recalculate color: fælles=red, child=green (frontend overrides with calColorMap anyway)
            has_child = any(c.startswith("cal-child-") for c in current_cals)
            target["color"] = "#43a047" if has_child else "#e53935"
            save_custom_events(all_events)
            # Update Google metadata in background
            t = dict(target)
            threading.Thread(target=_sync_google_event, args=(t,), daemon=True).start()
            return {"ok": True, "deleted": False, "remaining_calendars": current_cals}
        else:
            all_events = [e for e in all_events if e.get("id") != event_id]
            save_custom_events(all_events)
            gid = target.get("google_event_id", "")
            if gid:
                threading.Thread(target=_delete_google_event, args=(gid,), daemon=True).start()
            return {"ok": True, "deleted": True}
    else:
        all_events = [e for e in all_events if e.get("id") != event_id]
        save_custom_events(all_events)
        gid = target.get("google_event_id", "") if target else ""
        if gid:
            threading.Thread(target=_delete_google_event, args=(gid,), daemon=True).start()
        return {"ok": True, "deleted": True}

@app.post("/api/parse-event")
async def parse_event(request: Request):
    data = await request.json()
    text = data.get("text", "")[:3000]
    today = datetime.now()

    # Try Claude API if key is set
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        prompt = f"""Udtræk dato, tidspunkt og en kort titel fra denne tekst.
Dagens dato er {today.strftime('%Y-%m-%d')}.
Returner KUN valid JSON uden forklaring eller markdown:
{{"hasDate": true/false, "title": "kort titel", "start": "YYYY-MM-DDTHH:MM" eller "YYYY-MM-DD", "end": "YYYY-MM-DDTHH:MM" eller "YYYY-MM-DD" eller null, "allDay": true/false}}
Hvis ingen dato findes, returner {{"hasDate": false}}.
Tekst:
{text}"""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": anthropic_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-20250514", "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]}
                )
                r.raise_for_status()
                content = r.json()["content"][0]["text"].strip().replace("```json","").replace("```","").strip()
                return json.loads(content)
        except Exception as e:
            log.warning(f"Claude parse failed: {e}")

    # Fallback: regex parser for Danish date formats
    return _parse_event_regex(text, today)


def _parse_event_regex(text: str, today: datetime) -> dict:
    import re
    DA_MONTHS = {"januar":1,"februar":2,"marts":3,"april":4,"maj":5,"juni":6,
                 "juli":7,"august":8,"september":9,"oktober":10,"november":11,"december":12}
    DA_DAYS   = {"mandag":0,"tirsdag":1,"onsdag":2,"torsdag":3,"fredag":4,"lørdag":5,"søndag":6}
    t = text.lower()

    # Extract time range: kl. 15:30 - 16:30 or kl. 15.30
    time_start, time_end = None, None
    m = re.search(r'kl\.?\s*(\d{1,2})[:.:](\d{2})\s*[-–]\s*(\d{1,2})[:.:](\d{2})', t)
    if m:
        time_start = f"{int(m.group(1)):02d}:{m.group(2)}"
        time_end   = f"{int(m.group(3)):02d}:{m.group(4)}"
    else:
        m = re.search(r'kl\.?\s*(\d{1,2})[:.:](\d{2})', t)
        if m:
            time_start = f"{int(m.group(1)):02d}:{m.group(2)}"

    date = None

    # "d. 22/5" or "d. 22. maj" or "25. juni 2026"
    m = re.search(r'd\.?\s*(\d{1,2})\.?\s*/\s*(\d{1,2})(?:\.?\s*(\d{4}))?', t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        if month < today.month or (month == today.month and day < today.day): year += 1
        date = datetime(year, month, day)

    if not date:
        m = re.search(r'(\d{1,2})\.?\s+(' + '|'.join(DA_MONTHS.keys()) + r')(?:\.?\s+(\d{4}))?', t)
        if m:
            day, month_name = int(m.group(1)), m.group(2)
            year = int(m.group(3)) if m.group(3) else today.year
            month = DA_MONTHS[month_name]
            if month < today.month or (month == today.month and day < today.day): year += 1
            date = datetime(year, month, day)

    # "fredag" / "på fredag" / "næste mandag"
    if not date:
        for day_name, day_num in DA_DAYS.items():
            if day_name in t or f"på {day_name}" in t:
                days_ahead = (day_num - today.weekday()) % 7 or 7
                if "næste" in t: days_ahead += 7
                date = today + __import__('datetime').timedelta(days=days_ahead)
                break

    # "om X dage/uger"
    if not date:
        m = re.search(r'om\s+(\d+)\s+(dag|dage|uge|uger)', t)
        if m:
            n = int(m.group(1)) * (7 if 'uge' in m.group(2) else 1)
            date = today + __import__('datetime').timedelta(days=n)

    if not date:
        return {"hasDate": False}

    # Build title — first sentence or first 60 chars
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    raw = lines[0] if lines else "Begivenhed"
    # Stop at first sentence ending
    for sep in ['. ', '! ', '? ', '\n']:
        idx = raw.find(sep)
        if 0 < idx < 60:
            raw = raw[:idx]
            break
    title = raw[:60].strip()

    date_str = date.strftime('%Y-%m-%d')
    start = f"{date_str}T{time_start}" if time_start else date_str
    end   = f"{date_str}T{time_end}"   if time_end   else None

    return {"hasDate": True, "title": title, "start": start, "end": end, "allDay": not bool(time_start)}


@app.get("/api/custom-events.ics")
def get_custom_events_ics():
    """ICS feed of all local custom events — subscribe in Google Calendar or iCloud."""
    from fastapi.responses import Response
    events = load_custom_events()
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    def fmt_dt(s: str) -> str:
        # "2026-06-25T15:30" or "2026-06-25"
        s = s.replace("-","").replace(":","").replace(" ","T")
        if "T" not in s:
            return f"DATE:{s}"
        if len(s) == 13:  # "20260625T1530"
            s += "00"
        return f"DATETIME:{s}"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Familieoverblik//DA",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Familieoverblik",
        "X-WR-CALDESC:Lokale begivenheder fra Familieoverblik",
    ]
    for e in events:
        uid = e.get("id", "") + "@familieoverblik"
        start = fmt_dt(e.get("start", ""))
        raw_end = e.get("end") or e.get("start", "")
        end = fmt_dt(raw_end)
        title = (e.get("title") or "").replace("\\","\\\\").replace(",","\\,").replace("\n","\\n")
        desc  = (e.get("description") or "").replace("\\","\\\\").replace(",","\\,").replace("\n","\\n")[:500]
        cal   = e.get("calendar","")
        cal_label = "Fælles" if cal == "cal-faelles" else cal.replace("cal-child-","Barn ")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE={start}",
            f"DTEND;VALUE={end}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{desc}",
            f"CATEGORIES:{cal_label}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines)
    return Response(content=body, media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "inline; filename=familieoverblik.ics"})


@app.get("/api/settings")
def get_settings():
    result = {
        "api_key":    os.getenv("API_KEY", ""),
        "anthropic_key": "***" if os.getenv("ANTHROPIC_API_KEY") else "",
        "dashboard_title": os.getenv("DASHBOARD_TITLE", "Hjem"),
        "accounts":   [],
        "google_calendars": [],
        "weather_lat": os.getenv("WEATHER_LAT", "56.127"),
        "weather_lon": os.getenv("WEATHER_LON", "10.178"),
        "google_client_id":     "***" if os.getenv("GOOGLE_CLIENT_ID") else "",
        "google_client_secret": "***" if os.getenv("GOOGLE_CLIENT_SECRET") else "",
        "google_oauth_connected": bool(os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")),
        "google_default_calendar_id": os.getenv("GOOGLE_DEFAULT_CALENDAR_ID", "primary"),
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


@app.post("/api/settings")
async def save_settings(request: Request):
    """Save settings to .env file and reload environment."""
    import secrets as sec
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

    # Remove blank/comment lines before rewriting
    lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]

    # API key — generate if empty
    api_key = data.get("api_key", "").strip()
    if not api_key:
        api_key = sec.token_hex(32)
    set_env("API_KEY", api_key)

    # Accounts — skriv kun dem der er udfyldt, ryd resten dynamisk
    # Fjern alle eksisterende MITID_USERNAME/IDENTITY nøgler
    lines = [l for l in lines if not (l.startswith("MITID_USERNAME") or l.startswith("MITID_IDENTITY") or l.startswith("# MITID_"))]
    for idx, acc in enumerate(data.get("accounts", [])[:20]):
        u, i = acc.get("username", "").strip(), acc.get("identity", "").strip()
        if u or i:
            suffix = "" if idx == 0 else f"_{idx+1}"
            lines.append(f"MITID_USERNAME{suffix}={u}")
            lines.append(f"MITID_IDENTITY{suffix}={i}")

    # Google Kalendere — skriv kun dem der er udfyldt
    lines = [l for l in lines if not (l.startswith("GOOGLE_CALENDAR_ICS") or l.startswith("GOOGLE_CALENDAR_NAME") or l.startswith("# GOOGLE_CALENDAR_"))]
    for idx, cal in enumerate(data.get("google_calendars", [])[:20]):
        url, name = cal.get("url", "").strip(), cal.get("name", "").strip()
        if url:
            suffix = "" if idx == 0 else f"_{idx+1}"
            lines.append(f"GOOGLE_CALENDAR_ICS{suffix}={url}")
            lines.append(f"GOOGLE_CALENDAR_NAME{suffix}={name}")

    # Google OAuth credentials
    gcid = data.get("google_client_id", "").strip()
    gcsc = data.get("google_client_secret", "").strip()
    if gcid and gcid != "***": set_env("GOOGLE_CLIENT_ID", gcid)
    if gcsc and gcsc != "***": set_env("GOOGLE_CLIENT_SECRET", gcsc)
    gcal_default = data.get("google_default_calendar_id", "").strip()
    if gcal_default: set_env("GOOGLE_DEFAULT_CALENDAR_ID", gcal_default)

    # Weather
    if data.get("weather_lat"): set_env("WEATHER_LAT", data["weather_lat"])
    if data.get("weather_lon"): set_env("WEATHER_LON", data["weather_lon"])
    title = data.get("dashboard_title", "Hjem").strip() or "Hjem"
    set_env("DASHBOARD_TITLE", title)
    os.environ["DASHBOARD_TITLE"] = title
    ak = data.get("anthropic_key", "").strip()
    if ak and ak != "***": set_env("ANTHROPIC_API_KEY", ak)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Reload env in current process
    from dotenv import load_dotenv
    load_dotenv(override=True)
    global API_KEY
    API_KEY = os.getenv("API_KEY", "")

    return {"ok": True, "api_key": api_key}



# ── Google OAuth ─────────────────────────────────────────────────────────────

GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_SCOPES = "https://www.googleapis.com/auth/calendar.events"

_google_token_cache: dict = {"token": "", "expires_at": 0.0}
_custom_events_lock = __import__("threading").Lock()  # guards custom_events.json r/w

def _get_google_access_token() -> str:
    """Return a valid Google access token, refreshing via refresh_token if needed."""
    import time, requests as req
    cache = _google_token_cache
    if cache["token"] and time.time() < cache["expires_at"] - 60:
        return cache["token"]

    refresh_token = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "")
    if not refresh_token:
        return ""

    r = req.post(GOOGLE_TOKEN_URL, data={
        "client_id":     os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=10)
    r.raise_for_status()
    tokens = r.json()
    access_token = tokens.get("access_token", "")
    expires_in   = tokens.get("expires_in", 3600)

    os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"] = access_token
    cache["token"]      = access_token
    cache["expires_at"] = time.time() + expires_in
    logging.getLogger("google_oauth").info("Access token refreshed")
    return access_token


def _fmt_google_dt(s: str, is_end_allday: bool = False) -> dict:
    """Convert 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM' to Google Calendar dateTime/date dict.
    For all-day end dates Google requires the day *after* the last day."""
    if "T" in s:
        return {"dateTime": s + ":00" if len(s) == 16 else s, "timeZone": "Europe/Copenhagen"}
    if is_end_allday:
        import datetime as dt
        d = dt.date.fromisoformat(s) + dt.timedelta(days=1)
        return {"date": d.isoformat()}
    return {"date": s}


def _sync_google_event(event: dict) -> str | None:
    """Create or update a Google Calendar event. Returns google_event_id or None."""
    import requests as req
    access_token = _get_google_access_token()
    if not access_token:
        return None

    cal_id = os.getenv("GOOGLE_DEFAULT_CALENDAR_ID", "primary")
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    local_id    = event.get("id", "")
    local_cals  = event.get("calendar", "")
    google_id   = event.get("google_event_id", "")
    title       = event.get("title", "")

    # Build title prefix from child calendars e.g. "(Aksel, Max) - Titel"
    child_names = []
    for cid in local_cals.split(","):
        cid = cid.strip()
        if cid.startswith("cal-child-"):
            prof_id = cid.replace("cal-child-", "")
            name = client.get_child_name(prof_id)
            if name:
                child_names.append(name)
    if child_names:
        title = f"({', '.join(child_names)}) - {title}"

    all_day = "T" not in event.get("start", "")
    end_raw = event.get("end") or event.get("start", "")
    body = {
        "summary":     title,
        "description": event.get("description", ""),
        "start":       _fmt_google_dt(event.get("start", "")),
        "end":         _fmt_google_dt(end_raw, is_end_allday=all_day),
        "extendedProperties": {
            "private": {
                "familieoverblik_id":        local_id,
                "familieoverblik_calendars": local_cals,
            }
        }
    }

    try:
        if google_id:
            # Update existing
            r = req.put(
                f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events/{google_id}",
                headers=headers, json=body, timeout=10
            )
        else:
            # Create new
            r = req.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events",
                headers=headers, json=body, timeout=10
            )
        r.raise_for_status()
        return r.json().get("id", "")
    except Exception as ex:
        logging.warning(f"Google Calendar sync failed: {ex}")
        return None


def _delete_google_event(google_event_id: str) -> bool:
    """Delete a Google Calendar event entirely."""
    import requests as req
    access_token = _get_google_access_token()
    if not access_token or not google_event_id:
        return False
    cal_id = os.getenv("GOOGLE_DEFAULT_CALENDAR_ID", "primary")
    try:
        r = req.delete(
            f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events/{google_event_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        return r.status_code in (200, 204)
    except Exception as ex:
        logging.warning(f"Google Calendar delete failed: {ex}")
        return False

@app.get("/api/google-oauth/calendars")
def google_oauth_calendars():
    """List user's Google calendars for the default calendar picker."""
    import requests as req
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


@app.get("/api/google-oauth/connect")
def google_oauth_connect(request: Request):
    """Return the Google OAuth authorization URL to redirect the user to."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(400, "GOOGLE_CLIENT_ID not configured")
    redirect_uri = "http://localhost:8000/auth/google/callback"
    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         GOOGLE_OAUTH_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    }
    from urllib.parse import urlencode
    url = GOOGLE_AUTH_URL + "?" + urlencode(params)
    return {"auth_url": url}


@app.get("/auth/google/callback")
def oauth_callback(request: Request, code: str = "", error: str = ""):
    """Handle Google OAuth callback - exchange code for tokens and save refresh_token."""
    if error:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/settings.html?oauth=error&reason={error}")
    if not code:
        raise HTTPException(400, "No code received")

    client_id     = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    redirect_uri  = "http://localhost:8000/auth/google/callback"

    import requests as req
    r = req.post(GOOGLE_TOKEN_URL, data={
        "code":          code,
        "client_id":     client_id,
        "client_secret": client_secret,
        "redirect_uri":  redirect_uri,
        "grant_type":    "authorization_code",
    }, timeout=10)
    r.raise_for_status()
    tokens = r.json()

    refresh_token = tokens.get("refresh_token", "")
    if not refresh_token:
        logging.warning("Google OAuth: no refresh_token — user may need to revoke access and reconnect")

    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    def _set(key, val):
        nonlocal lines
        for i, l in enumerate(lines):
            if l.startswith(f"{key}="):
                lines[i] = f"{key}={val}"; return
        lines.append(f"{key}={val}")

    if refresh_token:
        _set("GOOGLE_OAUTH_REFRESH_TOKEN", refresh_token)
    _set("GOOGLE_OAUTH_ACCESS_TOKEN", tokens.get("access_token", ""))
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(env_path, override=True)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="http://familiekalender.local:8000/settings.html?oauth=success")


app.mount("/", StaticFiles(directory=str(Path(__file__).parent.parent / "frontend"), html=True), name="static")
