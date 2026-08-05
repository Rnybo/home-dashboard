"""
routers/aula.py — Aula endpoints (login, profile, messages, presence, calendar, posts, gallery, groups)
"""
import json
import logging
import os
import urllib.parse
from pathlib import Path

import requests as req
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

router = APIRouter()
ROOT = Path(__file__).parent.parent.parent


def _get_client():
    from backend.main import client
    return client


def _get_auth():
    from backend.main import aula_auth
    return aula_auth


def aula_call(fn):
    try:
        return fn()
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        if "403" in str(e) or "401" in str(e):
            raise HTTPException(status_code=401, detail="Session expired")
        raise HTTPException(status_code=500, detail=str(e))


# ── Login ─────────────────────────────────────────────────────────────────────

@router.get("/api/login/accounts")
def login_accounts():
    from backend.aula_auth import _load_tokens, _get_accounts
    tokens = _load_tokens()
    accounts = []
    for suffix in [""] + [f"_{i}" for i in range(2, 11)]:
        identity = os.getenv(f"MITID_IDENTITY{suffix}", "")
        username = os.getenv(f"MITID_USERNAME{suffix}", "")
        if username:
            name = identity.split()[0] if identity else username
            has_token = username in tokens
            accounts.append({"index": len(accounts), "name": name, "username": username, "has_token": has_token})
    return accounts


@router.post("/api/switch-account")
def switch_account(account_index: int = 0):
    from backend.aula_auth import _load_tokens, _get_accounts
    accounts = _get_accounts()
    if account_index >= len(accounts):
        raise HTTPException(status_code=400, detail="Invalid account index")
    username = accounts[account_index]["username"]
    tokens = _load_tokens()
    account_tokens = tokens.get(username, {})
    cookies = account_tokens.get("cookies", {})
    phpsessid = cookies.get("PHPSESSID", "")
    csrf = cookies.get("Csrfp-Token", "")
    if not phpsessid or not csrf:
        raise HTTPException(status_code=401, detail="No session for this account — please log in first")
    _get_client().update_credentials(phpsessid, csrf)
    logging.getLogger("switch").info(f"Switched to account: {username}")
    return {"ok": True, "name": accounts[account_index].get("identity", username).split()[0]}


@router.post("/api/login/start")
async def login_start(account_index: int = 0):
    _get_auth().start_login(account_index=account_index)
    return {"ok": True}


@router.get("/api/login/status")
def login_status():
    return _get_auth().get_status()


@router.post("/api/login/cancel")
async def login_cancel():
    _get_auth().cancel()
    return {"ok": True}


@router.post("/api/logout")
def logout():
    p = ROOT / "session.json"
    if p.exists():
        p.write_text(json.dumps({}))
    # update_credentials requires (phpsessid, csrf_token) — calling it with a
    # single dict arg raised a TypeError on every logout attempt (500 error,
    # logout never actually worked).
    _get_client().update_credentials("", "")
    return {"ok": True}


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/api/profile-config")
def profile_config():
    def fn():
        data = _get_client().get_profile().get("data", {})
        institutions = data.get("institutions") or []
        children, inst_profile_ids = [], []
        for inst in institutions:
            inst_profile_ids.append(inst.get("institutionProfileId"))
            for child in inst.get("children") or []:
                children.append({
                    "id":       child.get("id"),
                    "name":     child.get("name", "").split()[0],
                    "photoUrl": child.get("profilePicture", {}).get("url", ""),
                })
        return {"children": children, "inst_profile_ids": [i for i in inst_profile_ids if i]}
    return aula_call(fn)


@router.get("/api/profile")
def profile():
    return aula_call(_get_client().get_profile)


# ── Messages ──────────────────────────────────────────────────────────────────

@router.get("/api/messages")
def messages(page: int = 0):
    def fn():
        threads = _get_client().get_threads(page)
        return [{"id": t["id"], "subject": t.get("subject", ""), "read": t.get("read", True)} for t in threads]
    return aula_call(fn)


@router.get("/api/messages/{thread_id}")
def thread(thread_id: int):
    return aula_call(lambda: _get_client().get_messages_for_thread(thread_id))


# ── Aula data ─────────────────────────────────────────────────────────────────

@router.get("/api/presence")
def presence(inst_profile_ids: str = "", from_date: str = "", to_date: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_presence(ids, from_date or None, to_date or None))


@router.get("/api/presence/pickup-responsibles")
def pickup_responsibles(child_ids: str = ""):
    ids = [int(i) for i in child_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_pickup_responsibles(ids))


@router.post("/api/presence/update")
async def update_presence(request: Request):
    data = await request.json()
    updates = data.get("updates", [])
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    results = []
    client = _get_client()
    for u in updates:
        try:
            # update_presence_template does a blocking requests.post — this handler is
            # async def, so without run_in_threadpool it would freeze the whole event
            # loop (cast, weather, everything) for the duration of each Aula call.
            ok = await run_in_threadpool(
                client.update_presence_template,
                institution_profile_id=int(u["childId"]),
                by_date=u["date"],
                entry_time=u.get("entryTime", ""),
                exit_time=u.get("exitTime", ""),
                exit_with=u.get("exitWith", ""),
                comment=u.get("comment", ""),
                repeat_pattern=u.get("repeatPattern", "never"),
            )
            results.append({"childId": u["childId"], "ok": ok})
        except PermissionError:
            raise HTTPException(status_code=401, detail="Session expired")
        except Exception as e:
            results.append({"childId": u["childId"], "ok": False, "error": str(e)})
    return results


@router.get("/api/calendar")
def calendar(inst_profile_ids: str = "", from_date: str = "", to_date: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_calendar_events(ids, from_date or None, to_date or None))


@router.get("/api/posts")
def posts(inst_profile_ids: str = "", index: int = 0):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_posts(ids, index))


@router.get("/api/important-dates")
def important_dates(inst_profile_ids: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_important_dates(ids))


@router.get("/api/birthdays")
def birthdays(inst_profile_ids: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_birthdays(ids))


# ── Gallery ───────────────────────────────────────────────────────────────────

@router.get("/api/gallery/albums")
def gallery_albums(inst_profile_ids: str = ""):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_albums(ids))


@router.get("/api/gallery/albums/{album_id}/media")
def gallery_album_media(album_id: int, inst_profile_ids: str = "", index: int = 0):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_album_media(album_id, ids, index))


@router.get("/api/gallery/user-media")
def gallery_user_media(inst_profile_ids: str = "", index: int = 0, limit: int = 12):
    ids = [int(i) for i in inst_profile_ids.split(",") if i]
    return aula_call(lambda: _get_client().get_user_media(ids, index, limit))


# ── Groups ────────────────────────────────────────────────────────────────────

@router.get("/api/groups")
def groups():
    return aula_call(_get_client().get_groups_cached)


@router.get("/api/groups/{group_id}/contacts")
def group_contacts(group_id: int):
    return aula_call(lambda: _get_client().get_contact_list(group_id))


# ── Routes (ORS) ──────────────────────────────────────────────────────────────

@router.get("/api/routes")
def routes():
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
            "name":    name,
            "lat":     float(os.getenv(f"ORS_DEST_{i}_LAT", "0")),
            "lon":     float(os.getenv(f"ORS_DEST_{i}_LON", "0")),
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
                    "label":    profile_labels[profile],
                    "duration": int(seg["duration"] / 60),
                    "distance": round(seg["distance"] / 1000, 1),
                }
            except Exception as ex:
                logging.warning(f"ORS {profile} to {dest['name']}: {ex}")
        result.append(dest_result)
    return result
