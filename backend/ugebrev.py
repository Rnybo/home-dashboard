"""
backend/ugebrev.py — Parser af ugentlige skoleskema-"ugebreve" (Aula-opslag,
delt klassevis) til kalenderevents for det barn opslaget faktisk blev delt til.

Ingen manuel barn-indstilling — se _find_calendar_tag_for_doc()/sync_ugebrev()
for hvordan det rette barn bestemmes automatisk. Kilden er et Google Docs-link
i opslagets/beskedens tekst (ikke en rigtig vedhæftning) med en tabel:
dag-kolonner × tidsblok-rækker. Se frontend/CLAUDE.md / dette moduls
docstrings for antagelser om formatet — det er set fra ÉT eksempel og kan
vise sig skævt for andre klasser/skoler.
"""
import logging
import re
import uuid
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from backend.store import load_custom_events, save_custom_events, save_ugebrev_note

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
    """Returnerer {"week": int|None, "days": {dagnavn: [(start,slut,titel), ...]},
    "body_text": str}.

    Antagelser (baseret på ét eksempel — kan vise sig skæve for andre klasser):
    - Første <table> i dokumentet er skematabellen.
    - Række 0 = dag-headers, kolonne 0 = tidspunkt-kolonne.
    - Dubletter af samme dagnavn (set i praksis — to "Fredag"-kolonner i
      kildedokumentet) kollapses til FØRSTE forekomst; senere ignoreres.
    - En celles sluttid = næste rækkes starttid (sidste række får 30 min).
    - "body_text" = al paragraf-/overskriftstekst UDENFOR selve tabellen —
      typisk ugentlige huskere/beskeder fra læreren, som skematabellen ikke
      har plads til. Vist via et info-ikon i skolekalenderen (se
      frontend/js/skolekalender.js).
    """
    soup = BeautifulSoup(html, "html.parser")
    week = parse_week_number(soup.get_text(" "))
    days = {d: [] for d in DAY_NAMES}
    table = next(iter(soup.find_all("table")), None)

    body_parts = []
    for tag in soup.find_all(["p", "h1", "h2", "h3"]):
        if table and tag.find_parent("table") is table:
            continue
        text = tag.get_text(" ", strip=True)
        if text:
            body_parts.append(text)
    body_text = "\n".join(body_parts)

    if not table:
        return {"week": week, "days": days, "body_text": body_text}
    rows = table.find_all("tr")
    if len(rows) < 2:
        return {"week": week, "days": days, "body_text": body_text}

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

    return {"week": week, "days": days, "body_text": body_text}


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


def _get_children(client):
    """Returnerer [{"id":.., "name":..}, ...] for alle børn på kontoen."""
    profile = client.get_profile().get("data", {})
    children = []
    for inst in profile.get("institutions") or []:
        for c in inst.get("children") or []:
            if c.get("id"):
                children.append({"id": c["id"], "name": (c.get("name") or "").split()[0] or "barn"})
    return children


def _find_calendar_tag_for_doc(client, doc_url):
    """Finder hvilket barn et opslag med `doc_url` faktisk blev delt til ved
    at forespørge Aula pr. barn — samme opdeling `get_posts()` i forvejen
    bruger — og se hvis barns opslagsliste indeholder det. Undgår at skulle
    kende/stole på et internt Aula-felt for "hvilken klasse/gruppe et opslag
    hører til", som ikke er bekræftet at eksistere i den offentlige respons.
    Der er bevidst INGEN manuel barn-indstilling — "opslaget der delte
    ugebrevet er kalenderen det hører til" er hele pointen."""
    for child in _get_children(client):
        posts = client.get_posts([child["id"]], index=0, limit=15).get("posts", [])
        for p in posts:
            content = p.get("content") or {}
            html = content.get("html") or content.get("text") or ""
            if find_doc_url(html) == doc_url:
                return f"cal-child-{child['id']}"
    return None


def _sync_core(client, calendar_tag, doc_url, anchor_date):
    """Fælles kerne — henter/parser dokumentet og (gen)opretter events plus
    en evt. brødtekst-note. Kilde-uafhængig med vilje: tager imod en
    allerede-bestemt kalender-tag + URL i stedet for selv at slå noget op,
    så både `sync_ugebrev_url()` (bruger-klik) og `sync_ugebrev()`
    (automatisk scanning) kan dele den uden at duplikere logik."""
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
    if schedule.get("body_text"):
        save_ugebrev_note(f"{calendar_tag}|{year}|{schedule['week']}", schedule["body_text"])
    logger.info(f"Ugebrev uge {schedule['week']}/{year}: {len(events)} events for {calendar_tag}")
    return {"found": True, "week": schedule["week"], "year": year, "events_created": len(events)}


def sync_ugebrev_url(client, doc_url, anchor_date_str=None):
    """Bruges af "🎒 Tilføj til skolekalender"-knappen — frontend har allerede
    udtrukket doc_url fra enten en besked (aula.js) eller et opslag
    (calendar.js). Bestemmer selv hvilket barn via `_find_calendar_tag_for_doc`
    — ingen barn-parameter, ingen indstilling at glemme at sætte."""
    calendar_tag = _find_calendar_tag_for_doc(client, doc_url)
    if not calendar_tag:
        return {"found": False,
                "message": "Kunne ikke se hvilket barn dette blev delt til — opslaget blev ikke "
                           "fundet blandt nogen af børnenes seneste opslag (kan skyldes at det er "
                           "en besked, ikke et opslag, eller at det er ældre end de sidste 15 opslag)."}
    anchor = date.fromisoformat(anchor_date_str[:10]) if anchor_date_str else date.today()
    return _sync_core(client, calendar_tag, doc_url, anchor)


def sync_ugebrev(client):
    """Automatisk scanning — tjekker ALLE børns seneste opslag for ét med et
    Google Docs-link, og synkroniserer det til PRÆCIS det barns kalender
    opslaget blev delt til. Håndterer flere børn i forskellige klasser
    uden videre: hvert barn med et matchende opslag får sit eget skema.
    Returnerer {"found": False, "message": ...} eller
    {"found": True, "results": [{"child_name":.., "week":.., ...}, ...]}."""
    results = []
    for child in _get_children(client):
        posts = client.get_posts([child["id"]], index=0, limit=15).get("posts", [])
        for p in posts:
            content = p.get("content") or {}
            html = content.get("html") or content.get("text") or ""
            url = find_doc_url(html)
            if url:
                anchor = date.fromisoformat(p["timestamp"][:10]) if p.get("timestamp") else date.today()
                result = _sync_core(client, f"cal-child-{child['id']}", url, anchor)
                result["child_name"] = child["name"]
                results.append(result)
                break  # kun det nyeste matchende opslag pr. barn
    if not results:
        return {"found": False, "message": "Intet opslag med et Google Docs-link fundet for nogen af børnene."}
    return {"found": True, "results": results}
