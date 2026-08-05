"""
routers/custom.py — Custom Events CRUD + parse-event + ICS feed
"""
import json
import logging
import os
import threading
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from backend.store import load_custom_events, save_custom_events
from backend.google_utils import _sync_google_event, _delete_google_event

log = logging.getLogger("custom_events")

router = APIRouter()


@router.get("/api/custom-events")
def get_custom_events():
    return load_custom_events()


@router.post("/api/custom-events")
async def add_custom_event(request: Request):
    data = await request.json()
    event = {
        "id":              str(uuid.uuid4()),
        "title":           data.get("title", "").strip(),
        "start":           data.get("start", ""),
        "end":             data.get("end") or None,
        "allDay":          data.get("allDay", False),
        "description":     data.get("description", ""),
        "color":           data.get("color", "#7c3aed"),
        "calendar":        data.get("calendar", ""),
        "google_event_id": "",
    }
    events = load_custom_events()
    events.append(event)
    save_custom_events(events)

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


@router.delete("/api/custom-events/{event_id}")
def delete_custom_event(event_id: str, calendar: str = ""):
    all_events = load_custom_events()
    target = next((e for e in all_events if e.get("id") == event_id), None)

    if target and calendar:
        current_cals = [c.strip() for c in target.get("calendar", "").split(",") if c.strip()]
        current_cals = [c for c in current_cals if c != calendar]

        if current_cals:
            target["calendar"] = ",".join(current_cals)
            has_child = any(c.startswith("cal-child-") for c in current_cals)
            target["color"] = "#43a047" if has_child else "#e53935"
            save_custom_events(all_events)
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

@router.post("/api/parse-event")
async def parse_event(request: Request):
    data = await request.json()
    text = data.get("text", "")[:3000]
    today = datetime.now()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        prompt = f"""Udtræk dato, tidspunkt og en kort titel fra denne tekst.
Dagens dato er {today.strftime('%Y-%m-%d')}.
Returner KUN valid JSON uden forklaring eller markdown:
{{"hasDate": true/false, "title": "kort titel", "start": "YYYY-MM-DDTHH:MM" eller "YYYY-MM-DD", "end": "YYYY-MM-DDTHH:MM" eller null, "allDay": true/false}}
Hvis ingen dato findes, returner {{"hasDate": false}}.
Tekst:
{text}"""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": anthropic_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-20250514", "max_tokens": 200,
                          "messages": [{"role": "user", "content": prompt}]}
                )
                r.raise_for_status()
                content = r.json()["content"][0]["text"].strip().replace("```json","").replace("```","").strip()
                return json.loads(content)
        except Exception as e:
            log.warning(f"Claude parse failed: {e}")
    return _parse_event_regex(text, today)


def _parse_event_regex(text: str, today: datetime) -> dict:
    import re
    DA_MONTHS = {"januar":1,"februar":2,"marts":3,"april":4,"maj":5,"juni":6,
                 "juli":7,"august":8,"september":9,"oktober":10,"november":11,"december":12}
    DA_DAYS   = {"mandag":0,"tirsdag":1,"onsdag":2,"torsdag":3,"fredag":4,"lørdag":5,"søndag":6}
    t = text.lower()
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
    if not date:
        for day_name, day_num in DA_DAYS.items():
            if day_name in t:
                days_ahead = (day_num - today.weekday()) % 7 or 7
                if "næste" in t: days_ahead += 7
                import datetime as _dt
                date = today + _dt.timedelta(days=days_ahead)
                break
    if not date:
        m = re.search(r'om\s+(\d+)\s+(dag|dage|uge|uger)', t)
        if m:
            import datetime as _dt
            n = int(m.group(1)) * (7 if 'uge' in m.group(2) else 1)
            date = today + _dt.timedelta(days=n)
    if not date:
        return {"hasDate": False}
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    raw = lines[0] if lines else "Begivenhed"
    for sep in ['. ', '! ', '? ', '\n']:
        idx = raw.find(sep)
        if 0 < idx < 60:
            raw = raw[:idx]; break
    title = raw[:60].strip()
    date_str = date.strftime('%Y-%m-%d')
    start = f"{date_str}T{time_start}" if time_start else date_str
    end   = f"{date_str}T{time_end}"   if time_end   else None
    return {"hasDate": True, "title": title, "start": start, "end": end, "allDay": not bool(time_start)}


@router.get("/api/custom-events.ics")
def get_custom_events_ics():
    events = load_custom_events()
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    def fmt_dt(s: str) -> str:
        s = s.replace("-","").replace(":","").replace(" ","T")
        if "T" not in s: return f"DATE:{s}"
        if len(s) == 13: s += "00"
        return f"DATETIME:{s}"

    lines = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Familieoverblik//DA",
             "CALSCALE:GREGORIAN","METHOD:PUBLISH","X-WR-CALNAME:Familieoverblik"]
    for e in events:
        uid   = e.get("id","") + "@familieoverblik"
        start = fmt_dt(e.get("start",""))
        end   = fmt_dt(e.get("end") or e.get("start",""))
        title = (e.get("title") or "").replace("\\","\\\\").replace(",","\\,").replace("\n","\\n")
        desc  = (e.get("description") or "").replace("\\","\\\\").replace(",","\\,").replace("\n","\\n")[:500]
        cal   = e.get("calendar","")
        cal_label = "Fælles" if cal == "cal-faelles" else cal.replace("cal-child-","Barn ")
        lines += ["BEGIN:VEVENT",f"UID:{uid}",f"DTSTAMP:{now}",
                  f"DTSTART;VALUE={start}",f"DTEND;VALUE={end}",
                  f"SUMMARY:{title}",f"DESCRIPTION:{desc}",f"CATEGORIES:{cal_label}","END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response(content="\r\n".join(lines), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": "inline; filename=familieoverblik.ics"})
