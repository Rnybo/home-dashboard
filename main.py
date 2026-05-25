import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Request, Depends, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
import spotify_service as sp
from dotenv import load_dotenv
from aula_client import AulaClient
from aula_playwright import AulaPlaywright
import os
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

app = FastAPI(docs_url=None, redoc_url=None)
client = AulaClient()
playwright_login = AulaPlaywright(on_success=client.update_credentials)

API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    logging.warning("API_KEY is not set — API is unprotected!")

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
    resp = FileResponse("static/index.html")
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
    return {"api_key": API_KEY}


@app.get("/api/status", dependencies=[Depends(check_api_key)])
def status():
    return {"session_valid": client.check_session()}


@app.get("/api/login/accounts", dependencies=[Depends(check_api_key)])
def login_accounts():
    accounts = []
    for suffix in ["", "_2", "_3", "_4", "_5"]:
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

    calendars = [
        {"url": os.getenv("GOOGLE_CALENDAR_ICS_RASMUS", ""), "name": "Rasmus", "color": "#e53935"},
        {"url": os.getenv("GOOGLE_CALENDAR_ICS_MAJA",   ""), "name": "Maja",   "color": "#8e24aa"},
        {"url": "https://calendar.google.com/calendar/ical/da.danish%23holiday%40group.v.calendar.google.com/public/basic.ics", "name": "Helligdag", "color": "#f59e0b"},
    ]
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



# ── Spotify ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def start_spotify_polling():
    asyncio.create_task(sp.polling_loop())


@app.get("/api/spotify/auth")
async def spotify_auth():
    return RedirectResponse(sp.get_auth_url())


@app.get("/api/spotify/callback")
async def spotify_callback(code: str = "", error: str = ""):
    if error or not code:
        return {"error": error or "no code"}
    await sp.exchange_code(code)
    return RedirectResponse("/?spotify=connected")


@app.get("/api/spotify/current")
async def spotify_current():
    return sp.get_cached_state()


@app.get("/api/spotify/devices")
async def spotify_devices():
    return await sp.get_devices()


@app.post("/api/spotify/play")
async def spotify_play():
    await sp.control("play"); return {"ok": True}

@app.post("/api/spotify/pause")
async def spotify_pause():
    await sp.control("pause"); return {"ok": True}

@app.post("/api/spotify/next")
async def spotify_next():
    await sp.control("next"); return {"ok": True}

@app.post("/api/spotify/previous")
async def spotify_previous():
    await sp.control("previous"); return {"ok": True}

@app.post("/api/spotify/transfer")
async def spotify_transfer(device_id: str):
    ok = await sp.transfer_playback(device_id)
    return {"ok": ok}


@app.websocket("/ws/spotify")
async def spotify_ws(websocket: WebSocket):
    await websocket.accept()
    # Send current state immediately on connect
    try:
        await websocket.send_json(sp.get_cached_state())
    except Exception:
        return

    async def push(state: dict):
        await websocket.send_json(state)

    sp.subscribe(push)
    try:
        while True:
            await websocket.receive_text()  # keep alive; client can send "ping"
    except WebSocketDisconnect:
        pass
    finally:
        sp.unsubscribe(push)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
