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
# En sektionsoverskrift skal starte med "Uge XX" og derefter enten stoppe,
# eller fortsætte med et klart skilletegn (bindestreg/kolon/punktum) — accepterer
# fx "Uge 33", "Uge 33.", "Uge 33 – Kragelundskolen", "Uge 33: skema", men
# afviser en almindelig sætning der blot NÆVNER en uge og fortsætter uden
# skilletegn (fx "Uge 33 var fantastisk, vi..."), som ellers ville splitte
# dokumentet forkert midt i en sektions brødtekst.
SECTION_HEADING_RE = re.compile(r"^[Uu]ge\s*[:.]?\s*(\d{1,2})\s*(?:[-–—:.]|$)")
DAY_ABBREVIATIONS = {
    "Man": "Mandag", "Tirs": "Tirsdag", "Ons": "Onsdag", "Tors": "Torsdag", "Fre": "Fredag",
}


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


def _parse_single_time(txt):
    """'8' / '8.00' / '13.30' -> '08:00' / '08:00' / '13:30'. En bar time uden
    minutter ('8') tolkes som hele timen ('08:00'). None hvis ikke parsbar."""
    m = re.match(r"^(\d{1,2})(?:[.:](\d{2}))?$", txt.strip())
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2)) if m.group(2) else 0
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return f"{h:02d}:{mi:02d}"


def _parse_time_range(txt):
    """Parser en tidscelle til (start, explicit_end|None). Tager imod et
    interval ('8-8.45', '8.00-8.45' — almindelig bindestreg ELLER en
    Unicode-dash, Google Docs' autokorrektur skriver nogle gange en anden
    dash-type end den man taster). Er kun ét tidspunkt angivet, er
    explicit_end None, og _parse_table() udleder i stedet sluttiden af næste
    rækkes start (bagudkompatibel adfærd). Et EKSPLICIT angivet sluttidspunkt
    respekteres derimod altid — uden det ville et hul i skemaet (fx et
    frikvarter uden sin egen række) fejlagtigt strække forrige aktivitet
    frem til den næste rækkes start."""
    parts = DASH_RE.split(txt.strip())
    start = _parse_single_time(parts[0])
    end = _parse_single_time(parts[1]) if len(parts) > 1 and parts[1].strip() else None
    return start, end


def _add_minutes(hhmm, minutes):
    h, m = map(int, hhmm.split(":"))
    total = (h * 60 + m + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _parse_table(table):
    """Parser én skematabel til {dagnavn: [(start,slut,titel), ...]}.

    Antagelser (baseret på ét eksempel — kan vise sig skæve for andre klasser):
    - Række 0 = dag-headers, kolonne 0 = tidspunkt-kolonne.
    - Dubletter af samme dagnavn (set i praksis — to "Fredag"-kolonner i
      kildedokumentet) kollapses til FØRSTE forekomst; senere ignoreres.
    - En celles sluttid er det EKSPLICIT angivne sluttidspunkt, hvis der er
      angivet et interval — ellers næste rækkes starttid (sidste række får
      30 min).
    """
    days = {d: [] for d in DAY_NAMES}
    if table is None:
        return days
    rows = table.find_all("tr")
    if len(rows) < 2:
        return days

    header_cells = rows[0].find_all(["td", "th"])
    col_day, seen = {}, set()
    for ci, cell in enumerate(header_cells[1:], start=1):
        # .capitalize() normaliserer "MANDAG"/"mandag"/"Mandag:" -> "Mandag"
        # så header-matchet ikke er afhængigt af kildedokumentets forskellige
        # skrivemåder (versaler varierer i praksis mellem klasser/skoler).
        # Tager også imod almindelige forkortelser ("Tirs", "Fre", ...).
        name = cell.get_text(strip=True).rstrip(":.").strip().capitalize()
        resolved = name if name in DAY_NAMES else DAY_ABBREVIATIONS.get(name)
        if resolved and resolved not in seen:
            col_day[ci] = resolved
            seen.add(resolved)

    time_rows = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        start_t, explicit_end = _parse_time_range(cells[0].get_text(strip=True))
        if start_t is not None:
            time_rows.append((start_t, explicit_end, cells))

    for ri, (start_t, explicit_end, cells) in enumerate(time_rows):
        if explicit_end:
            end_t = explicit_end
        elif ri + 1 < len(time_rows):
            end_t = time_rows[ri + 1][0]
        else:
            end_t = _add_minutes(start_t, 30)
        for ci, day in col_day.items():
            if ci >= len(cells):
                continue
            title = cells[ci].get_text(separator=" ", strip=True)
            if title:
                days[day].append((start_t, end_t, title))
    return days


def split_document_into_weeks(html):
    """Splitter et Google Docs-dokument i separate uge-sektioner. Skolen
    genbruger i praksis ÉT løbende dokument og tilføjer bare en ny "Uge XX"-
    overskrift for hver uge i stedet for at lave et nyt dokument hver gang —
    uden denne opsplitning ville brødteksten (og for et dokument med flere
    tabeller, skemaet) blande ALLE ugers indhold sammen, uanset hvilken uge
    man reelt kiggede på.

    Returnerer [{"week": int|None, "tables": [<Tag>, ...], "body_text": str}, ...]
    i dokumentets rækkefølge — "tables" er ALLE tabeller i sektionen, ikke kun
    den første, fordi en lærer kan sætte en anden tabel (fx en note-tabel)
    før selve skematabellen; parse_document() prøver dem i rækkefølge og
    bruger den første der reelt giver indhold. Et dokument uden eksplicitte
    "Uge XX"-overskrifter (kun ét ugebrev, ingen akkumulering) giver én
    sektion med week=None og alt indhold samlet — matcher tidligere adfærd
    for den slags dokumenter.
    """
    soup = BeautifulSoup(html, "html.parser")
    # find_all bevarer dokument-rækkefølgen på tværs af tag-typer. Filtreringen
    # udelukker <p>/<hN> der reelt ligger INDE i en tabel (Google Docs-export
    # pakker celletekst i <p>-tags), så tabellens indhold ikke optræder to
    # gange — én gang som del af <table>, én gang som løsrevet paragraf.
    elements = soup.find_all(["h1", "h2", "h3", "p", "table"])
    flow = [el for el in elements if el.name == "table" or not el.find_parent("table")]

    sections = []
    current = None
    for el in flow:
        if el.name != "table":
            text = el.get_text(" ", strip=True)
            m = SECTION_HEADING_RE.match(text)
            if m:
                current = {"week": int(m.group(1)), "tables": [], "body_parts": []}
                sections.append(current)
                continue
        if current is None:
            current = {"week": None, "tables": [], "body_parts": []}
            sections.append(current)
        if el.name == "table":
            current["tables"].append(el)
        else:
            text = el.get_text(" ", strip=True)
            if text:
                current["body_parts"].append(text)

    return [{"week": s["week"], "tables": s["tables"], "body_text": "\n".join(s["body_parts"])}
            for s in sections]


def parse_document(html):
    """Parser hele dokumentet til én skema-dict PR. uge fundet i det (se
    split_document_into_weeks). Returnerer [{"week":.., "days":{...},
    "body_text":..}, ...] — springer sektioner uden noget ugenummer over.
    Prøver hver tabel i en sektion i rækkefølge og bruger den første der
    reelt giver mindst én udfyldt tidsblok — falder tilbage til en tom dict
    hvis ingen tabel i sektionen kan tolkes (fx en note-tabel uden dage)."""
    sections = split_document_into_weeks(html)
    results = []
    for s in sections:
        if not s["week"]:
            continue
        days = {d: [] for d in DAY_NAMES}
        for table in s["tables"]:
            parsed = _parse_table(table)
            if any(blocks for blocks in parsed.values()):
                days = parsed
                break
        results.append({"week": s["week"], "days": days, "body_text": s["body_text"]})
    return results


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
    target_id = _doc_id(doc_url)
    for child in _get_children(client):
        posts = client.get_posts([child["id"]], index=0, limit=15).get("posts", [])
        for p in posts:
            content = p.get("content") or {}
            html = content.get("html") or content.get("text") or ""
            found_url = find_doc_url(html)
            # Sammenlign dokument-ID, IKKE hele URL-strengen — Google kan
            # variere query-parametre (fx "usp=sharing" vs. "usp=drive_link")
            # for samme dokument, hvilket ville få et eksakt strengmatch til
            # fejlagtigt at afvise et reelt match.
            if found_url and target_id and _doc_id(found_url) == target_id:
                return f"cal-child-{child['id']}"
    return None


def _sync_core(client, calendar_tag, doc_url, anchor_date):
    """Fælles kerne — henter dokumentet og (gen)opretter events + brødtekst-
    noter for HVER uge fundet i det (se parse_document/split_document_into_weeks
    — skolen genbruger typisk ét løbende dokument for hele skoleåret). Kilde-
    uafhængig med vilje: tager imod en allerede-bestemt kalender-tag + URL i
    stedet for selv at slå noget op, så både `sync_ugebrev_url()` (bruger-klik)
    og `sync_ugebrev()` (automatisk scanning) kan dele den uden at duplikere
    logik. `anchor_date` bruges til årsopløsning for HVER uge for sig."""
    html = fetch_doc_html(doc_url)
    schedules = parse_document(html)
    if not schedules:
        return {"found": False,
                "message": "Fandt dokumentet, men kunne ikke læse noget ugenummer i det (forventer 'Uge XX')."}

    weeks_synced = []
    for schedule in schedules:
        dates = resolve_week_dates(anchor_date, schedule["week"])
        year = dates["Mandag"].year
        events = build_events(schedule, dates, calendar_tag, year)
        if events:
            replace_ugebrev_events(events, calendar_tag, schedule["week"], year)
        if schedule.get("body_text"):
            save_ugebrev_note(f"{calendar_tag}|{year}|{schedule['week']}", schedule["body_text"])
        weeks_synced.append({"week": schedule["week"], "year": year, "events_created": len(events)})

    total_events = sum(w["events_created"] for w in weeks_synced)
    logger.info(f"Ugebrev-dokument for {calendar_tag}: {len(weeks_synced)} uge(r), {total_events} events i alt")
    return {"found": True, "weeks": weeks_synced, "events_created": total_events}


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
    {"found": True, "results": [{"child_name":.., "weeks":[...], "events_created":..}, ...]}."""
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
