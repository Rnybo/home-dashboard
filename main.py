import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Request, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")
