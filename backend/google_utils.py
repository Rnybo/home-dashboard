"""
backend/google_utils.py — Google Calendar hjælpefunktioner
Adskilt fra main.py for at undgå circular imports
"""
import logging
import os
import time

import requests as req

GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_SCOPES = "https://www.googleapis.com/auth/calendar.events"

_google_token_cache: dict = {"token": "", "expires_at": 0.0}


def _get_google_access_token() -> str:
    cache = _google_token_cache
    if cache["token"] and time.time() < cache["expires_at"] - 60:
        return cache["token"]
    refresh_token = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "")
    if not refresh_token:
        return ""
    try:
        r = req.post(GOOGLE_TOKEN_URL, data={
            "client_id":     os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "refresh_token": refresh_token,
            "grant_type":    "refresh_token",
        }, timeout=10)
        r.raise_for_status()
        tokens = r.json()
    except Exception as e:
        # Callers treat "" the same as "not connected" — without this, an
        # invalid/revoked refresh_token raises an unhandled HTTPError here,
        # and several call sites (e.g. /api/google-oauth/calendars) don't
        # wrap this specific call, so it surfaced as a raw 500 instead of
        # a graceful "not connected" response.
        logging.getLogger("google_oauth").warning(f"Token refresh failed: {e}")
        return ""
    access_token = tokens.get("access_token", "")
    expires_in   = tokens.get("expires_in", 3600)
    os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"] = access_token
    cache["token"]      = access_token
    cache["expires_at"] = time.time() + expires_in
    logging.getLogger("google_oauth").info("Access token refreshed")
    return access_token


def _fmt_google_dt(s: str, is_end_allday: bool = False) -> dict:
    if "T" in s:
        return {"dateTime": s + ":00" if len(s) == 16 else s, "timeZone": "Europe/Copenhagen"}
    if is_end_allday:
        import datetime as dt
        d = dt.date.fromisoformat(s) + dt.timedelta(days=1)
        return {"date": d.isoformat()}
    return {"date": s}


def _sync_google_event(event: dict) -> str | None:
    access_token = _get_google_access_token()
    if not access_token:
        return None
    # Reuse the global client singleton (already has session + cached profile)
    # instead of constructing a throwaway AulaClient(), which used to force an
    # extra, unnecessary Aula API call on every single background sync just to
    # look up a child's first name.
    try:
        from backend.main import client as _client
    except Exception:
        _client = None

    cal_id  = os.getenv("GOOGLE_DEFAULT_CALENDAR_ID", "primary")
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    local_id   = event.get("id", "")
    local_cals = event.get("calendar", "")
    google_id  = event.get("google_event_id", "")
    title      = event.get("title", "")

    child_names = []
    for cid in local_cals.split(","):
        cid = cid.strip()
        if cid.startswith("cal-child-") and _client:
            name = _client.get_child_name(cid.replace("cal-child-", ""))
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
        "extendedProperties": {"private": {
            "familieoverblik_id":        local_id,
            "familieoverblik_calendars": local_cals,
        }}
    }
    try:
        if google_id:
            r = req.put(f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events/{google_id}",
                        headers=headers, json=body, timeout=10)
        else:
            r = req.post(f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events",
                         headers=headers, json=body, timeout=10)
        r.raise_for_status()
        return r.json().get("id", "")
    except Exception as ex:
        logging.warning(f"Google Calendar sync failed: {ex}")
        return None


def _delete_google_event(google_event_id: str) -> bool:
    access_token = _get_google_access_token()
    if not access_token or not google_event_id:
        return False
    cal_id = os.getenv("GOOGLE_DEFAULT_CALENDAR_ID", "primary")
    try:
        r = req.delete(
            f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events/{google_event_id}",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=10
        )
        return r.status_code in (200, 204)
    except Exception as ex:
        logging.warning(f"Google Calendar delete failed: {ex}")
        return False
