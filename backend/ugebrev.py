"""
backend/ugebrev.py — Parser af ugentlige skoleskema-"ugebreve" fra Aula-beskeder
til kalenderevents for et valgt barn.

Kilden er typisk et Google Docs-link i beskedteksten (ikke en rigtig vedhæftning)
med en tabel: dag-kolonner × tidsblok-rækker. Se frontend/CLAUDE.md / dette
moduls docstrings for antagelser om formatet — det er set fra ÉT eksempel og
kan vise sig skævt for andre klasser/skoler.
"""
import logging
import re
import uuid
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from backend.store import load_custom_events, save_custom_events

logger = logging.getLogger("ugebrev")

DAY_NAMES = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"]
WEEK_RE = re.compile(r"[Uu]ge\s*[:.]?\s*(\d{1,2})\b")
DOC_URL_RE = re.compile(r'https://docs\.google\.com/document/d/[\w-]+[^\s"\'<>]*')
EVENT_COLOR = "#e65100"  # bevidst afvigende farve — nem at få øje på og slette

# Nøgleord → ikon. Rækkefølgen betyder noget — første match vinder, så mere
# specifikke ord står højere end generiske. Baseret på ÉT eksempeldokument
# (0. klasse) — udvid listen frem for at omskrive matching-logikken når nye
# ugebreve viser ord der ikke er dækket.
ICON_KEYWORDS = [
    (["første skoledag", "velkommen i"], "🎒"),
    (["fejrer", "fødselsdag"], "🎉"),
    (["morgenbånd", "rundkreds", "morgensang"], "🌅"),
    (["frugt"], "🍎"),
    (["madpakke"], "🥪"),
    (["bibliotek"], "📚"),
    (["bevægelse", "bingo", "idræt"], "🤾"),
    (["tegn", "farvelæg", "måler"], "🎨"),
    (["trylleshow"], "🎩"),
    (["ferie"], "🏖️"),
    (["sfo"], "🏠"),
    (["frikvarter", "legetid", "lege"], "🤸"),
]
DEFAULT_ICON = "📋"
LEADING_TIME_RE = re.compile(r"^\d{1,2}[.:]\d{2}\s+")
DASH_RE = re.compile(r"[-\u2010-\u2015]")  # bindestreg + alle Unicode-dash-varianter


def _icon_for(title):
    low = title.lower()
    for keywords, icon in ICON_KEYWORDS:
        if any(k in low for k in keywords):
            return icon
    return DEFAULT_ICON


def _clean_title(title):
    """Fjerner et evt. gentaget klokkeslæt forrest i celleteksten (kilden
    gentager ofte tiden inde i selve cellen, fx '9.30 Frugt') — vi har
    allerede tiden fra tidspunkt-kolonnen, det er bare støj i en
    børnevenlig, ikon-første titel."""
    return LEADING_TIME_RE.sub("", title).strip()


def find_doc_url(html_or_text):
    """Finder det første Google Docs-link i en beskeds HTML/tekst-indhold."""
    if not html_or_text:
        return None
    m = DOC_URL_RE.search(html_or_text)
    return m.group(0) if m else None


def _doc_id(doc_url):
    m = re.search(r"/document/d/([\w-]+)", doc_url)
    return m.group(1) if m else None


def fetch_doc_html(doc_url, timeout=15):
    """Henter et delt Google Docs-dokument som ren HTML (kræver 'alle med link
    kan se' — ingen login understøttet). Kaster ved fejl."""
    doc_id = _doc_id(doc_url)
    if not doc_id:
        raise ValueError(f"Kunne ikke finde dokument-id i URL: {doc_url}")
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    r = requests.get(export_url, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_week_number(doc_text):
    m = WEEK_RE.search(doc_text)
    return int(m.group(1)) if m else None


def _parse_time(txt):
    """'8' / '8.00' / '13.30' -> '08:00' / '08:00' / '13:30'. Tager også imod
    et interval ('8-8.45', '8.00-8.45' — almindelig bindestreg ELLER en
    Unicode-dash, Google Docs' autokorrektur skriver nogle gange en anden
    dash-type end den man taster) og bruger kun starten, som altid regnes
    sammen med næste rækkes start i parse_schedule(). En bar time uden
    minutter ('8') tolkes som hele timen ('08:00'). None hvis ikke parsbar."""
    txt = DASH_RE.split(txt.strip())[0].strip()
    m = re.match(r"^(\d{1,2})(?:[.:](\d{2}))?$", txt)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2)) if m.group(2) else 0
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return f"{h:02d}:{mi:02d}"


def _add_minutes(hhmm, minutes):
    h, m = map(int, hhmm.split(":"))
    total = (h * 60 + m + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_schedule(html):
    """Returnerer {"week": int|None, "days": {dagnavn: [(start,slut,titel), ...]}}.

    Antagelser (baseret på ét eksempel — kan vise sig skæve for andre klasser):
    - Første <table> i dokumentet er skematabellen.
    - Række 0 = dag-headers, kolonne 0 = tidspunkt-kolonne.
    - Dubletter af samme dagnavn (set i praksis — to "Fredag"-kolonner i
      kildedokumentet) kollapses til FØRSTE forekomst; senere ignoreres.
    - En celles sluttid = næste rækkes starttid (sidste række får 30 min).
    """
    soup = BeautifulSoup(html, "html.parser")
    week = parse_week_number(soup.get_text(" "))
    days = {d: [] for d in DAY_NAMES}

    tables = soup.find_all("table")
    if not tables:
        return {"week": week, "days": days}
    rows = tables[0].find_all("tr")
    if len(rows) < 2:
        return {"week": week, "days": days}

    header_cells = rows[0].find_all(["td", "th"])
    col_day, seen = {}, set()
    for ci, cell in enumerate(header_cells[1:], start=1):
        # .capitalize() normaliserer "MANDAG"/"mandag"/"Mandag:" -> "Mandag"
        # så header-matchet ikke er afhængigt af kildedokumentets forskellige
        # skrivemåder (versaler varierer i praksis mellem klasser/skoler).
        name = cell.get_text(strip=True).rstrip(":.").strip().capitalize()
        if name in DAY_NAMES and name not in seen:
            col_day[ci] = name
            seen.add(name)

    time_rows = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        t = _parse_time(cells[0].get_text(strip=True))
        if t is not None:
            time_rows.append((t, cells))

    for ri, (start_t, cells) in enumerate(time_rows):
        end_t = time_rows[ri + 1][0] if ri + 1 < len(time_rows) else _add_minutes(start_t, 30)
        for ci, day in col_day.items():
            if ci >= len(cells):
                continue
            title = cells[ci].get_text(separator=" ", strip=True)
            if title:
                days[day].append((start_t, end_t, title))

    return {"week": week, "days": days}


def resolve_week_dates(anchor_date, week):
    """Returnerer {dagnavn: date} for man-fre i ISO-uge `week`. Vælger det år
    hvis mandag lander tættest på `anchor_date` — værner mod årsskifte-tvivl
    (fx en besked sendt i december der nævner "Uge 1", som hører til det
    kommende år, ikke det indeværende)."""
    best = None
    for candidate_year in (anchor_date.year - 1, anchor_date.year, anchor_date.year + 1):
        try:
            monday = date.fromisocalendar(candidate_year, week, 1)
        except ValueError:
            continue
        distance = abs((monday - anchor_date).days)
        if best is None or distance < best[0]:
            best = (distance, monday)
    if best is None:
        raise ValueError(f"Ugyldigt ugenummer: {week}")
    monday = best[1]
    return {DAY_NAMES[i]: monday + timedelta(days=i) for i in range(5)}


def build_events(schedule, dates, calendar_tag, year):
    events = []
    for day, blocks in schedule["days"].items():
        d = dates.get(day)
        if not d:
            continue
        for start_t, end_t, title in blocks:
            clean = _clean_title(title)
            icon = _icon_for(clean)
            events.append({
                "id": str(uuid.uuid4()),
                "title": f"{icon} {clean}",
                "start": f"{d.isoformat()}T{start_t}",
                "end": f"{d.isoformat()}T{end_t}",
                "allDay": False,
                "description": "",
                "color": EVENT_COLOR,
                "calendar": calendar_tag,
                "google_event_id": "",
                "source": "ugebrev",
                "ugebrev_week": schedule["week"],
                "ugebrev_year": year,
            })
    return events


def replace_ugebrev_events(new_events, calendar_tag, week, year):
    """Idempotent: fjerner tidligere auto-genererede events for præcis denne
    barn+uge+år-kombination før de nye indsættes. En gentaget/rettet sync
    overskriver kun sig selv — rører aldrig andre uger eller manuelt
    oprettede events."""
    events = load_custom_events()
    events = [
        e for e in events
        if not (e.get("source") == "ugebrev" and e.get("calendar") == calendar_tag
                and e.get("ugebrev_week") == week and e.get("ugebrev_year") == year)
    ]
    events.extend(new_events)
    save_custom_events(events)


def _sync_core(client, child_id, doc_url, anchor_date):
    """Fælles kerne — henter/parser dokumentet og (gen)opretter events.
    Kilde-uafhængig med vilje: "ugebrev" er set optræde som BÅDE en Aula
    *besked* og et Aula *opslag* (to helt forskellige datamodeller/API'er) —
    ved at tage imod en allerede-udtrukket URL i stedet for selv at slå
    tråd/opslag op server-side, virker denne funktion uanset hvilken af de to
    kilden var, og for enhver fremtidig tredje kilde uden ændringer her."""
    calendar_tag = f"cal-child-{child_id}"

    html = fetch_doc_html(doc_url)
    schedule = parse_schedule(html)
    if not schedule["week"]:
        return {"found": False,
                "message": "Fandt dokumentet, men kunne ikke læse et ugenummer i det (forventer 'Uge XX')."}

    dates = resolve_week_dates(anchor_date, schedule["week"])
    year = dates["Mandag"].year

    events = build_events(schedule, dates, calendar_tag, year)
    if not events:
        return {"found": True, "week": schedule["week"], "year": year, "events_created": 0,
                "message": "Dokumentet blev læst, men ingen udfyldte tidsblokke blev fundet — "
                           "skematabellen kan have et andet format end forventet."}

    replace_ugebrev_events(events, calendar_tag, schedule["week"], year)
    logger.info(f"Ugebrev uge {schedule['week']}/{year}: {len(events)} events for {calendar_tag}")
    return {"found": True, "week": schedule["week"], "year": year, "events_created": len(events)}


def sync_ugebrev_url(client, child_id, doc_url, anchor_date_str=None):
    """Bruges af "🎒 Tilføj til skolekalender"-knappen — frontend har allerede
    udtrukket doc_url fra enten en besked (aula.js) eller et opslag
    (calendar.js), ingen server-side tråd/opslag-opslag nødvendig."""
    anchor = date.fromisoformat(anchor_date_str[:10]) if anchor_date_str else date.today()
    return _sync_core(client, child_id, doc_url, anchor)


def sync_ugebrev(client, child_id, subject_match="ugebrev"):
    """Baggrunds-/manuel scanning uden en bestemt besked/opslag at gå ud fra.
    Prøver OPSLAG først — det er hvor et "ugebrev" typisk rent faktisk ligger
    (delt med hele klassen, ikke en privat besked) — og falder tilbage til
    beskedtråde med emnematch. Se `_sync_core()`s docstring for hvorfor disse
    to kilder begge skal understøttes."""
    posts = client.get_posts([int(child_id)], index=0, limit=15).get("posts", [])
    for p in posts:
        content = p.get("content") or {}
        html = content.get("html") or content.get("text") or ""
        url = find_doc_url(html)
        if url:
            anchor = date.fromisoformat(p["timestamp"][:10]) if p.get("timestamp") else date.today()
            return _sync_core(client, child_id, url, anchor)

    threads = []
    for page in range(3):
        batch = client.get_threads(page=page)
        if not batch:
            break
        threads.extend(batch)
    match = next((t for t in threads if subject_match.lower() in (t.get("subject") or "").lower()), None)
    if not match:
        return {"found": False,
                "message": f"Fandt hverken et opslag med et Google Docs-link eller en tråd med "
                           f"'{subject_match}' i emnet blandt de seneste."}

    data = client.get_messages_for_thread(match["id"])
    doc_url, msg_date_str = None, None
    for m in data.get("messages", []):
        text = m.get("text") or {}
        html = text.get("html") if isinstance(text, dict) else text
        url = find_doc_url(html)
        if url:
            doc_url, msg_date_str = url, m.get("sendDateTime")
            break
    if not doc_url:
        return {"found": False,
                "message": f"Fandt tråden '{match.get('subject')}', men intet Google Docs-link i den."}

    anchor = date.fromisoformat(msg_date_str[:10]) if msg_date_str else date.today()
    return _sync_core(client, child_id, doc_url, anchor)
