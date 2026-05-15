from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from aula_client import AulaClient
import os

load_dotenv()

app = FastAPI()
client = AulaClient()

API_KEY = os.getenv("API_KEY", "")


def check_api_key(request: Request):
    if not API_KEY:
        return  # No key configured, allow all (dev mode)
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


class SessionUpdate(BaseModel):
    phpsessid: str
    csrf_token: str


@app.get("/bookmarklet", response_class=HTMLResponse)
def bookmarklet():
    html = open("static/bookmarklet.html").read()
    return html.replace("%%API_KEY%%", API_KEY)


@app.get("/api/config")
def config():
    """Expose API key to the frontend (served server-side, not in static files)."""
    return {"api_key": API_KEY}


@app.get("/api/status")
def status(request: Request):
    check_api_key(request)
    valid = client.check_session()
    return {"session_valid": valid}


@app.post("/api/refresh-session")
def refresh_session(request: Request, body: SessionUpdate):
    check_api_key(request)
    client.update_credentials(body.phpsessid, body.csrf_token)
    valid = client.check_session()
    if not valid:
        raise HTTPException(status_code=401, detail="New credentials rejected by Aula")
    return {"ok": True}


@app.get("/api/profile")
def profile(request: Request):
    check_api_key(request)
    try:
        return client.get_profile()
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/messages")
def messages(request: Request, page: int = 0):
    check_api_key(request)
    try:
        threads = client.get_threads(page)
        return [{"id": t["id"], "subject": t.get("subject", ""), "read": t.get("read", True)} for t in threads]
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/messages/{thread_id}")
def thread(request: Request, thread_id: int):
    check_api_key(request)
    try:
        return client.get_messages_for_thread(thread_id)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendar")
def calendar(request: Request, inst_profile_ids: str = ""):
    check_api_key(request)
    try:
        ids = [int(i) for i in inst_profile_ids.split(",") if i]
        return client.get_calendar_events(ids)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/", StaticFiles(directory="static", html=True), name="static")
