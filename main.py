from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from aula_client import AulaClient
from aula_playwright import AulaPlaywright
import os

load_dotenv()

app = FastAPI()
client = AulaClient()

API_KEY = os.getenv("API_KEY", "")


def check_api_key(request: Request):
    if not API_KEY:
        return
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


async def on_login_success(phpsessid: str, csrf_token: str):
    client.update_credentials(phpsessid, csrf_token)


playwright_login = AulaPlaywright(on_success=on_login_success)


@app.get("/api/config")
def config():
    return {"api_key": API_KEY}


@app.get("/api/status")
def status(request: Request):
    check_api_key(request)
    valid = client.check_session()
    return {"session_valid": valid}


@app.post("/api/login/start")
async def login_start(request: Request):
    check_api_key(request)
    playwright_login.start_login()
    return {"ok": True, "message": "Login started — check MitID app"}


@app.get("/api/login/status")
def login_status(request: Request):
    check_api_key(request)
    return playwright_login.get_status()


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
