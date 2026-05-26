import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Request, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from backend.aula_client import AulaClient
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
ROOT = Path(__file__).parent.parent  # project root (aula-dashboard/)
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
playwright_login = AulaPlaywright(on_success=client.update_credentials)

API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    logging.warning("API_KEY is not set — API is unprotected!")

async def _session_keepalive():
    """Ping Aula every 6 hours to keep session alive."""
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            valid = client.check_session()
            logging.getLogger("keepalive").info(f"Session keepalive: {'OK' if valid else 'EXPIRED'}")
        except Exception as e:
            logging.getLogger("keepalive").warning(f"Keepalive failed: {e}")

@app.on_event("startup")
async def startup():
    asyncio.create_task(_session_keepalive())

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

    colors = ["#e53935","#8e24aa","#1e88e5","#43a047","#fb8c00"]
    seen, calendars = set(), []
    for idx in range(1, 11):
        suffix = "" if idx == 1 else f"_{idx}"
        url  = os.getenv(f"GOOGLE_CALENDAR_ICS{suffix}", "")
        name = os.getenv(f"GOOGLE_CALENDAR_NAME{suffix}", f"Kalender {idx}")
        if url and url not in seen:
            seen.add(url); calendars.append({"url": url, "name": name, "color": colors[min(idx-1, len(colors)-1)]})
    calendars.append({"url": "https://calendar.google.com/calendar/ical/da.danish%23holiday%40group.v.calendar.google.com/public/basic.ics", "name": "Helligdag", "color": "#f59e0b"})
    today = datetime.date.today()
    date_from = datetime.date.fromisoformat(from_date) if from_date else today
    date_to   = datetime.date.fromisoformat(to_date)   if to_date   else today + datetime.timedelta(days=6)

    events = []
    for cal in calendars:
        if not cal["url"]:
            continue
        try:
            r = req.get(cal["url"], timeout=8)
            r.raise_for_status()
            gcal = Calendar.from_ical(r.content)
            import recurring_ical_events
            components = recurring_ical_events.of(gcal).between(date_from, date_to)
            for component in components:
                if component.name != "VEVENT":
                    continue
                dtstart = component.get("DTSTART")
                dtend   = component.get("DTEND")
                if not dtstart:
                    continue
                val = dtstart.dt
                all_day = not hasattr(val, "hour")
                start_iso = val.isoformat() if all_day else val.astimezone().isoformat()
                end_val = dtend.dt if dtend else val
                end_iso = end_val.isoformat() if all_day else (end_val.astimezone().isoformat() if hasattr(end_val, 'hour') else end_val.isoformat())
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
            headers={"User-Agent": "aula-dashboard/1.0 github.com/Rnybo/aula-dashboard"},
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
    try:    return json.loads(CUSTOM_EVENTS_FILE.read_text(encoding="utf-8"))
    except: return []

def save_custom_events(events: list):
    CUSTOM_EVENTS_FILE.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/custom-events")
def get_custom_events():
    return load_custom_events()

@app.post("/api/custom-events")
async def add_custom_event(request: Request):
    data = await request.json()
    import uuid
    event = {
        "id":          str(uuid.uuid4()),
        "title":       data.get("title", "").strip(),
        "start":       data.get("start", ""),
        "end":         data.get("end") or None,
        "allDay":      data.get("allDay", False),
        "description": data.get("description", ""),
        "color":       data.get("color", "#7c3aed"),
        "calendar":    data.get("calendar", ""),
    }
    events = load_custom_events()
    events.append(event)
    save_custom_events(events)
    return {"ok": True, "id": event["id"]}

@app.delete("/api/custom-events/{event_id}")
def delete_custom_event(event_id: str):
    events = [e for e in load_custom_events() if e.get("id") != event_id]
    save_custom_events(events)
    return {"ok": True}

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


app.mount("/", StaticFiles(directory=str(Path(__file__).parent.parent / "frontend"), html=True), name="static")
