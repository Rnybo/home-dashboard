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
import os
import re
import uuid
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from backend.store import load_custom_events, save_custom_events, save_ugebrev_note, load_ugebrev_notes

logger = logging.getLogger("ugebrev")

DAY_NAMES = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"]
DOC_URL_RE = re.compile(r'https://docs\.google\.com/document/d/[\w-]+[^\s"\'<>]*')
EVENT_COLOR = "#e65100"  # bevidst afvigende farve — nem at få øje på og slette
SFO_EVENT_COLOR = "#00838f"  # tydeligt anderledes end skole-orange — SFO skal kunne skelnes ved blikket
SFO_ICON = "🏠"

# Et Aula-opslag genkendes som et ugebrev/ugeplan alene på TITLEN — langt mere
# robust end at lede efter mønstre nede i selve indholdet, som varierer meget
# mellem lærere/pædagoger (tabel, ren tekst, eller et rent billede).
WEEKLY_LETTER_TITLE_RE = re.compile(r"ugebrev|ugeplan", re.IGNORECASE)
# Simpelt "alle tal i titlen" i stedet for en snæver "uge \d+"-regex — dækker
# både "Ugebrev uge 34 (og 35)" (ordet "uge" optræder) og "Ugebrev 35" (gør
# det ikke), uden at skulle gætte på alle skrivemåder. Titler er korte og har
# i praksis ingen andre tal end ugenumre.
TITLE_NUMBER_RE = re.compile(r"\d{1,2}")

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


def replace_ugebrev_events(new_events, calendar_tag, week, year, source="ugebrev"):
    """Idempotent: fjerner tidligere auto-genererede events for præcis denne
    barn+uge+år+KILDE-kombination før de nye indsættes. En gentaget/rettet
    sync overskriver kun sig selv — rører aldrig andre uger, andre kilder
    (fx et SFO-billede rører ikke skolens ugebrev-tabel for samme uge, da de
    er reelt forskelligt indhold der skal kunne sameksistere) eller manuelt
    oprettede events."""
    events = load_custom_events()
    events = [
        e for e in events
        if not (e.get("source") == source and e.get("calendar") == calendar_tag
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


def _is_weekly_letter_post(title):
    return bool(WEEKLY_LETTER_TITLE_RE.search(title or ""))


def _weeks_from_title(title):
    """'Ugebrev uge 34 (og 35)' -> [34, 35]; 'Ugebrev 35' -> [35];
    'Ugeplan uge 35' -> [35]. Ingen tal i titlen -> []."""
    weeks = []
    for n in TITLE_NUMBER_RE.findall(title or ""):
        w = int(n)
        if 1 <= w <= 53 and w not in weeks:
            weeks.append(w)
    return weeks


def _own_children_for_post(client, post):
    """Finder hvilke(t) EGET/egne barn/børn et opslag hører til via Aulas
    egen `sharedWithGroups` (gruppen/klassen opslaget faktisk er delt med).
    To trin:
      1. Hurtig sti — slå op mod `client.get_groups_cached()`, som allerede
         kender hvilke børn (inkl. isOwnChild) der sidder i hver "direkte"
         klasse-gruppe (dækker almindelige klasse-ugebreve uden ekstra kald).
      2. Falder tilbage til `client.get_group_member_ids()` (live opslag)
         for grupper der IKKE findes i den cache — fx tværklasse "årgang"-
         grupper (set i praksis: en SFO-ugeplan delt med "0. årgang forældre"
         i stedet for en enkelt klasse), som `get_groups()` bevidst udelader
         fordi den kun bruges til kontaktlisten/hovedgrupper.
    Langt mere robust end at gætte ud fra dokument-indhold (se den ældre
    `_find_calendar_tag_for_doc`, som stadig bruges af den manuelle "🎒
    Tilføj til skolekalender"-knap for beskeder uden gruppe-info)."""
    shared = post.get("sharedWithGroups") or post.get("shared_with_groups") or []
    if not shared:
        return []
    own_children = {c["id"]: c["name"] for c in _get_children(client)}

    try:
        groups = client.get_groups_cached() or []
    except Exception as e:
        logger.warning(f"Kunne ikke hente grupper til barne-opløsning: {e}")
        groups = []
    by_id, by_name = {}, {}
    for g in groups:
        if g.get("id") is not None:
            by_id[g["id"]] = g
        name = (g.get("name") or "").strip().lower()
        if name:
            by_name[name] = g

    found = {}
    for sg in shared:
        gid = sg.get("id") or sg.get("groupId")
        gname = (sg.get("name") or "").strip().lower()
        group = by_id.get(gid) or by_name.get(gname)
        if group:
            for ch in group.get("children") or []:
                if ch.get("isOwnChild") and ch.get("id") and ch["id"] not in found:
                    found[ch["id"]] = (ch.get("name") or "").split()[0] or "barn"
            continue
        if gid is not None:
            member_ids = client.get_group_member_ids(gid)
            matched = {cid for cid in own_children if cid in member_ids}
            if not matched:
                # Gruppen matcher ingen af vores børns egne institutionsprofil-
                # ID'er — men for en GUARDIAN-niveau-gruppe (fx "0. årgang
                # forældre") består medlemslisten af FORÆLDRES profiler, ikke
                # børnenes, så det opslag kan aldrig matches den vej. Tjekker
                # derfor om VI (som guardian) selv er medlem — er vi det,
                # dækker gruppen typisk en hel årgang, og vi kan ikke se
                # hvilket specifikt barn opslaget gælder ud fra medlemskabet
                # alene, så det antages med vilje at gælde ALLE vores børn
                # (mere retvisende end at droppe opslaget helt, se eksemplet
                # med SFO-ugeplanen delt med "0. årgang forældre").
                try:
                    guardian_ids = set(client._get_guardian_profile_ids())
                except Exception:
                    guardian_ids = set()
                if guardian_ids & member_ids:
                    matched = set(own_children)
            for cid in matched:
                if cid not in found:
                    found[cid] = own_children[cid].split()[0] if own_children[cid] else "barn"
    return [{"id": cid, "name": name} for cid, name in found.items()]


def _post_image_urls(post):
    """Fuld-opløsnings billed-URL'er fra et opslags vedhæftninger (matcher
    feltnavnene `renderAttachments()` i frontend/js/calendar.js allerede
    bruger) — bruges til SFO/ugeplan-billeder, hvor selve billedet ER
    indholdet, ikke en vedhæftning til et dokument."""
    urls = []
    for a in post.get("attachments") or []:
        media = a.get("media") or {}
        file_info = media.get("file") or a.get("file") or {}
        url = file_info.get("url") or media.get("largeThumbnailUrl") or media.get("thumbnailUrl") or a.get("url")
        if url:
            urls.append(url)
    return urls


def _configure_tesseract():
    """Lokaliserer tesseract-binær'en. På Linux/Termux (fremtidig tablet-
    kørsel) ligger den allerede på PATH efter `pkg install tesseract`, så
    ingenting skal gøres der. På Windows er den typisk IKKE i PATH efter
    installation — tjekker kendte install-stier, samt en valgfri
    TESSERACT_CMD miljøvariabel til manuel override."""
    import pytesseract
    cmd = os.getenv("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        return
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ):
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


_DAY_HEADER_WORDS = {
    "mandag": "Mandag", "tirsdag": "Tirsdag", "onsdag": "Onsdag",
    "torsdag": "Torsdag", "fredag": "Fredag",
}


def _ocr_parse_weekplan_image(image_bytes):
    """Lokal OCR-aflæsning af en billed-ugeplan (SFO/klasse) via Tesseract —
    INGEN AI-API, ingen netværkskald, ingen nøgle. Returnerer samme form som
    før: {"is_sfo": bool, "days": {"Mandag": ["aktivitet", ...], ...}} eller
    None hvis billedet ikke ligner en genkendelig dag-tabel (fx Tesseract
    ikke installeret, eller billedet ikke har ugedags-overskrifter).

    Fremgangsmåde: Tesseracts ordvise bounding-bokse (`image_to_data`) bruges
    til først at finde de fem ugedags-overskrifters x-position — det
    etablerer kolonnegrænserne — og derefter placeres al tekst UNDER
    overskrifterne i den kolonne hvis overskrift ligger tættest på (x-
    afstand). Simplere end at forsøge at rekonstruere hele tabel-layoutet,
    men robust nok til det observerede billedformat (fast dag-header-række +
    aktivitetstekst/ikoner i cellerne nedenunder)."""
    try:
        import io
        from PIL import Image
        import pytesseract
    except ImportError as e:
        logger.warning(f"OCR-afhængigheder mangler ({e}) — pip install pytesseract Pillow")
        return None

    _configure_tesseract()
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        data = pytesseract.image_to_data(img, lang="dan+eng", output_type=pytesseract.Output.DICT)
    except Exception as e:
        # Dækker bl.a. manglende tesseract-binær og manglende sprogpakke
        # ("dan.traineddata") — springer billedet over i stedet for at fejle
        # hele syncen.
        logger.warning(f"OCR af ugeplan-billede fejlede: {e}")
        return None

    n = len(data["text"])
    day_columns = {}   # dagnavn -> x-center af overskriften
    header_bottom = 0
    for i in range(n):
        word = data["text"][i].strip().lower().rstrip(":.")
        if word in _DAY_HEADER_WORDS:
            day = _DAY_HEADER_WORDS[word]
            if day not in day_columns:
                day_columns[day] = data["left"][i] + data["width"][i] / 2
                header_bottom = max(header_bottom, data["top"][i] + data["height"][i])

    if not day_columns:
        return None  # ingen ugedags-overskrifter fundet — ikke en dag-tabel

    # Kolonne-tildeling sker PR. ORD, ikke pr. Tesseract-"linje" — Tesseracts
    # egen linje-gruppering (block_num/par_num/line_num) kan i praksis spænde
    # på tværs af flere fysiske kolonner i en tabel uden cellekanter (set:
    # en hel visuel række på tværs af alle 5 dage blev læst som ÉN Tesseract-
    # linje, hvis gennemsnitlige x-center så fejlagtigt lagde HELE rækken i
    # én enkelt dag-kolonne). Ved at tildele kolonne pr. ord først, og selv
    # klynge ord til rækker BAGEFTER (kun inden for hver kolonnes egne ord),
    # er dette ikke længere afhængigt af Tesseracts linje-gætning.
    words_by_day = {d: [] for d in day_columns}
    is_sfo = False
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        if "sfo" in text.lower():
            is_sfo = True
        if data["top"][i] < header_bottom + 3:
            continue  # selve dag-header-rækken, ikke indhold
        x_center = data["left"][i] + data["width"][i] / 2
        nearest_day = min(day_columns, key=lambda d: abs(day_columns[d] - x_center))
        words_by_day[nearest_day].append({
            "left": data["left"][i], "top": data["top"][i],
            "bottom": data["top"][i] + data["height"][i], "text": text,
        })

    if not any(words_by_day.values()):
        return {"is_sfo": is_sfo, "days": {}}

    all_heights = sorted(w["bottom"] - w["top"] for words in words_by_day.values() for w in words)
    median_height = all_heights[len(all_heights) // 2] if all_heights else 20
    ROW_GAP_FACTOR = 0.6    # ord tættere end dette (× median-ordhøjde) hører til SAMME visuelle linje
    MERGE_GAP_FACTOR = 1.4  # linjer tættere end dette hører til SAMME aktivitet (flerlinjet tekst,
                            # fx "Mountainbike med" / "Kevin") — adskilt fra NÆSTE aktivitet i
                            # samme kolonne af den større afstand et klip-art-billede giver.

    day_texts = {}
    for day, words in words_by_day.items():
        words.sort(key=lambda w: w["top"])

        # Trin 1: klynge ord til visuelle rækker/linjer ud fra vertikal nærhed
        # — erstatter Tesseracts (upålidelige, se ovenfor) egen linjegruppering.
        rows, current_words, current_bottom = [], [], None
        for w in words:
            if current_words and (w["top"] - current_bottom) <= median_height * ROW_GAP_FACTOR:
                current_words.append(w)
            else:
                if current_words:
                    rows.append(current_words)
                current_words = [w]
            current_bottom = max(current_bottom or 0, w["bottom"])
        if current_words:
            rows.append(current_words)

        row_lines = []
        for row_words in rows:
            row_words.sort(key=lambda w: w["left"])
            row_lines.append({
                "top": min(w["top"] for w in row_words),
                "bottom": max(w["bottom"] for w in row_words),
                "text": " ".join(w["text"] for w in row_words),
            })

        # Trin 2: sammenlæg flerlinjede aktiviteter til ét kalenderpunkt.
        activities, current_text, current_bottom = [], None, None
        for line in row_lines:
            if current_text is not None and (line["top"] - current_bottom) <= median_height * MERGE_GAP_FACTOR:
                current_text += " " + line["text"]
            else:
                if current_text is not None:
                    activities.append(current_text)
                current_text = line["text"]
            current_bottom = line["bottom"]
        if current_text is not None:
            activities.append(current_text)
        if activities:
            day_texts[day] = activities

    return {"is_sfo": is_sfo, "days": day_texts}



def _build_events_from_days_dict(days_dict, dates, calendar_tag, year, week, is_sfo):
    """Bygger heldagsevents fra OCR'ens {"Mandag": ["aktivitet", ...], ...}-
    svar. Heldagsevents med vilje — billed-ugeplaner angiver typisk ikke
    klokkeslæt, kun dag+aktivitet, i modsætning til tabel-ugebrevet."""
    events = []
    color = SFO_EVENT_COLOR if is_sfo else EVENT_COLOR
    for day, activities in (days_dict or {}).items():
        resolved_day = day if day in DAY_NAMES else DAY_ABBREVIATIONS.get(day.strip().capitalize())
        d = dates.get(resolved_day) if resolved_day else None
        if not d or not activities:
            continue
        for activity in activities:
            icon = SFO_ICON if is_sfo else _icon_for(activity)
            events.append({
                "id": str(uuid.uuid4()),
                "title": f"{icon} {activity}".strip(),
                "start": f"{d.isoformat()}T00:00",
                "end": f"{d.isoformat()}T23:59",
                "allDay": True,
                "description": "",
                "color": color,
                "calendar": calendar_tag,
                "google_event_id": "",
                "source": "sfo_ugebrev" if is_sfo else "ugebrev_billede",
                "ugebrev_week": week,
                "ugebrev_year": year,
            })
    return events


def _should_resync(existing_notes, existing_events, calendar_tag, year, week, today, sources=("ugebrev",)):
    """Springer en uge over hvis den allerede er synkroniseret (under en af
    `sources`) OG ikke er "den nærmeste" (indeværende/næste uge, hvor
    rettelser fra skolen oftest sker) — se ønsket i punkt 3: kun manglende
    uger, eller den seneste, gensynkroniseres ved hver kørsel, i stedet for
    hele dokumentets historik hver gang."""
    monday = resolve_week_dates(today, week)["Mandag"]
    is_nearest = abs((monday - today).days) <= 10
    key = f"{calendar_tag}|{year}|{week}"
    has_note = key in existing_notes
    has_events = any(
        e.get("source") in sources and e.get("calendar") == calendar_tag
        and e.get("ugebrev_week") == week and e.get("ugebrev_year") == year
        for e in existing_events
    )
    return is_nearest or not (has_note or has_events)


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


def sync_ugebrev(client, limit=20):
    """Automatisk scanning — går det FÆLLES opslagsfeed igennem (ét kald,
    ikke ét pr. barn), genkender ugebreve/ugeplaner alene på TITLEN
    (`_is_weekly_letter_post`), og finder selv hvilke(t) barn/børn de hører
    til via `_own_children_for_post` (Aulas `sharedWithGroups` slået op mod
    `groups_cache.json`) — dækker også opslag delt bredt til fx "0. årgang",
    som rammer flere børn på én gang.

    Et opslags indhold håndteres forskelligt afhængig af hvad det rent
    faktisk indeholder (ikke alle ugebreve ligner hinanden — se samtale/
    eksempler fra august 2026):
      1. Google Docs-link MED en brugbar tabel  -> eksisterende tabel-parser,
         men kun for de uger titlen faktisk nævner (undgår at hele dokumentets
         historik bliver gensynkroniseret hver gang — se `_should_resync`).
      2. Et rent billede (ugeplan/SFO)          -> lokal Tesseract-OCR læser
         dag→aktivitet ud af billedet; `is_sfo` afgør ikon/farve/kilde, så
         SFO kan skelnes fra skolens eget skema.
      3. Hverken tabel eller billede            -> selve opslagsteksten gemmes
         som brødtekst-note (samme sted info-ikonet henter fra) — dækker fx
         et ugebrev der kun er løbende tekst, ingen tabel.

    Returnerer {"found": False, "message": ...} eller
    {"found": True, "results": [{"child_name":.., "weeks":[...], "events_created":.., ["sfo": bool]}, ...]}."""
    children = _get_children(client)
    if not children:
        return {"found": False, "message": "Ingen børn fundet på kontoen."}

    posts = client.get_posts([c["id"] for c in children], index=0, limit=limit).get("posts", [])
    # Ældste først: Aula returnerer nyeste-først, men skoler sender ofte
    # overlappende "kombi-ugebreve" (fx "uge 33 (og 34)" efterfulgt senere af
    # "uge 34 (og 35)") — begge rører uge 34. Ved at behandle ældste post
    # først vinder det NYESTE opslags version for en delt uge (sidste skriv
    # vinder), i stedet for at det er tilfældigt hvilket opslag der "vandt"
    # baseret på feed-rækkefølge — se testfund august 2026.
    posts = sorted(posts, key=lambda p: p.get("timestamp") or "")
    today = date.today()
    existing_notes = load_ugebrev_notes()
    existing_events = load_custom_events()
    results = []

    for p in posts:
        title = p.get("title") or ""
        if not _is_weekly_letter_post(title):
            continue
        resolved_children = _own_children_for_post(client, p)
        if not resolved_children:
            continue

        weeks_in_title = _weeks_from_title(title)
        content = p.get("content") or {}
        html = content.get("html") or content.get("text") or ""
        doc_url = find_doc_url(html)
        image_urls = _post_image_urls(p)
        anchor = date.fromisoformat(p["timestamp"][:10]) if p.get("timestamp") else today
        # Kun beregnet én gang pr. opslag — bruges hvis hverken tabel eller
        # billede giver noget indhold (gren 3 ovenfor).
        plain_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True) if html else ""

        for child in resolved_children:
            calendar_tag = f"cal-child-{child['id']}"
            handled = False

            # ── Gren 1: Google Docs-link med tabel ──────────────────────────
            if doc_url:
                try:
                    schedules = parse_document(fetch_doc_html(doc_url))
                except Exception as e:
                    logger.warning(f"Kunne ikke hente/parse dokument for '{title}': {e}")
                    schedules = []
                if weeks_in_title:
                    schedules = [s for s in schedules if s["week"] in weeks_in_title]
                if any(any(blocks) for s in schedules for blocks in s["days"].values()):
                    week_results = []
                    for schedule in schedules:
                        dates = resolve_week_dates(anchor, schedule["week"])
                        year = dates["Mandag"].year
                        if not _should_resync(existing_notes, existing_events, calendar_tag, year,
                                               schedule["week"], today, sources=("ugebrev",)):
                            continue
                        events = build_events(schedule, dates, calendar_tag, year)
                        if events:
                            replace_ugebrev_events(events, calendar_tag, schedule["week"], year, source="ugebrev")
                        note_text = schedule.get("body_text") or plain_text
                        if note_text:
                            save_ugebrev_note(f"{calendar_tag}|{year}|{schedule['week']}", note_text)
                        week_results.append({"week": schedule["week"], "year": year, "events_created": len(events)})
                    if week_results:
                        results.append({"child_name": child["name"], "weeks": week_results,
                                         "events_created": sum(w["events_created"] for w in week_results)})
                        handled = True

            # ── Gren 2: billede (ugeplan/SFO) ───────────────────────────────
            if not handled and image_urls and weeks_in_title:
                for w in weeks_in_title:
                    dates = resolve_week_dates(anchor, w)
                    year = dates["Mandag"].year
                    if not _should_resync(existing_notes, existing_events, calendar_tag, year, w, today,
                                           sources=("sfo_ugebrev", "ugebrev_billede")):
                        continue
                    try:
                        resp = client.session.get(image_urls[0], timeout=20)
                        resp.raise_for_status()
                        parsed = _ocr_parse_weekplan_image(resp.content)
                    except Exception as e:
                        logger.warning(f"Kunne ikke hente ugeplan-billede: {e}")
                        parsed = None
                    if not parsed:
                        continue
                    is_sfo = bool(parsed.get("is_sfo"))
                    source = "sfo_ugebrev" if is_sfo else "ugebrev_billede"
                    events = _build_events_from_days_dict(parsed.get("days"), dates, calendar_tag, year, w, is_sfo)
                    if events:
                        replace_ugebrev_events(events, calendar_tag, w, year, source=source)
                        results.append({"child_name": child["name"], "sfo": is_sfo,
                                         "weeks": [{"week": w, "year": year, "events_created": len(events)}],
                                         "events_created": len(events)})
                        handled = True

            # ── Gren 3: hverken tabel eller billede — gem ren tekst ─────────
            if not handled and plain_text and weeks_in_title:
                for w in weeks_in_title:
                    dates = resolve_week_dates(anchor, w)
                    year = dates["Mandag"].year
                    if not _should_resync(existing_notes, existing_events, calendar_tag, year, w, today,
                                           sources=("ugebrev", "ugebrev_billede", "sfo_ugebrev")):
                        continue
                    save_ugebrev_note(f"{calendar_tag}|{year}|{w}", plain_text)
                    results.append({"child_name": child["name"],
                                     "weeks": [{"week": w, "year": year, "events_created": 0}],
                                     "events_created": 0})

    if not results:
        return {"found": False, "message": "Intet ugebrev/ugeplan-opslag krævede synkronisering."}
    return {"found": True, "results": results}
