# backend/routers/ — API endpoints

> **Status:** Living document. Dækker i dag: `aula.py`, `custom.py`, `google.py`, `settings.py`, `spotify.py`, `weather.py`, `news.py`, `cast.py`.

Alle routers importerer den globale `client`/`aula_auth` fra `backend/main.py` via lazy `from backend.main import ...` inde i funktionerne (ikke top-level) for at undgå circular imports — følg samme mønster i nye routers.

## `aula.py` — Aula-data (login, profil, beskeder, kalender, galleri, klasser, presence)

- **`aula_call(fn)`** er standard-wrapperen for alle Aula-kald: fanger `PermissionError` → 401, alt andet → 500. Brug den for nye endpoints i stedet for at håndtere fejl manuelt.
- **`update_presence`** kører de blokerende Aula-kald via `run_in_threadpool` (se `backend/CLAUDE.md`s afsnit om kørselsmodel) — ikke fordi det er "bedste praksis" generelt, men fordi denne specifikke handler er `async def` og ellers fryser hele serveren.
- **`logout()`** kalder `client.update_credentials("", "")` — **skal være to argumenter**. Blev tidligere kaldt med ét (en dict), hvilket gav en `TypeError` og en 500 på hvert logout-forsøg.
- `/api/routes` (ORS) kalder tre profiler (cykel/gang/bil) sekventielt per destination — fejler enkeltvist og lydløst per profil (logges), resten af svaret er stadig brugbart.

## `custom.py` — Custom events (CRUD, ICS-feed, AI-parsing)

- **`/api/parse-event`** prøver Claude API først (hvis `ANTHROPIC_API_KEY` sat), falder tilbage til en dansk regex-parser (`_parse_event_regex`) hvis Claude-kaldet fejler eller ingen nøgle er sat. Regex-parseren forstår danske månedsnavne, ugedage, "om X dage/uger", `d. DD/MM` og `kl. HH:MM[-HH:MM]`.
- Google Calendar-sync for custom events sker i baggrundstråde (`threading.Thread(daemon=True)`) — fyld-og-glem, ingen fejlrapportering tilbage til brugeren hvis Google-sync fejler (det er en bevidst best-effort-sync, ikke kritisk sti).
- Brug `log` (modul-niveau logger, `logging.getLogger("custom_events")`) til fejl her — ikke en lokal variabel, den findes ikke i funktions-scope.

## `google.py` — Google Calendar (ICS-læsning) + OAuth

- Læser Google Calendar via **offentlige ICS-links** (ikke API), plus en hardcoded dansk helligdagskalender. `_normalize_vevent()` håndterer en lang række edge cases (all-day vs. tidsbaseret, manglende DTEND, naive datetimes, DURATION i stedet for DTEND) — hvis kalenderevents ser forskudt eller forkerte ud, start her.
- OAuth-callback (`/auth/google/callback`) skriver tokens direkte til `.env`-filen (ikke `tokens.json` som Aula) og genindlæser den med `load_dotenv(override=True)`.

## `settings.py` — Indstillinger

- `.env`-skrivning bruger et generisk `set_env(key, value)`-mønster (find linje med `KEY=`, opdater, eller tilføj) — dette mønster er dupliceret i `google.py` og `spotify.py`'s OAuth-callbacks. Hvis du tilføjer endnu et sted der skriver til `.env`, overvej at udtrække det til en delt hjælpefunktion.
- `google_calendars`-listen bevares hvis `save_settings()` modtager en tom liste (undgår at en tom gem-handling sletter eksisterende kalendere).

## `spotify.py` — Spotify OAuth + søgning + afspilning

- `/api/spotify/play` skelner mellem enkelt-track (`spotify:track:...`) og context (album/playliste/show) baseret på URI-prefix — bruger `context_uri` for alt andet end enkelt-tracks.

## `weather.py`, `news.py` — Vejr (met.no) og nyheder (DR RSS)

- **Ingen caching** i `weather.py` — hvert dashboard-poll rammer met.no direkte. met.no forventer at man ikke poller unødigt ofte; tjek at frontend's poll-interval er rimeligt (se `frontend/js/CLAUDE.md` når det er skrevet).
- **`/api/article-extract`** henter en DR-artikel server-side og udtrækker læsbar tekst med BeautifulSoup (`itemprop="articleBody"` — schema.org-markup DR selv bruger, virker konsistent på tværs af deres forskellige sideskabeloner — testet på både korte "seneste"-nyheder og lange sportsartikler). Findes fordi to enklere tilgange begge blev bekræftet **ikke virker** på den faktiske tablet: iframe-indlejring (DR sender `X-Frame-Options`) og `window.open()`/ny fane (understøttes ikke af Fully Kiosk Browser). Fjerner scripts/nav/forms fra det udtrukne indhold — dels for at undgå frame-busting-lignende JS, dels fordi vi kun vil have læsevisning. Begrænset til `dr.dk`-domænet, ligesom `/api/file-proxy` er begrænset til `aula.dk`.

## `cast.py` — Chromecast state + WebSocket

- Har et fuldt **mock-mode** (`CAST_MOCK=1` i `.env`) med simulerede enheder og afspilning — praktisk til UI-udvikling uden fysiske Cast-enheder tilgængelige.
- `/api/cast/{device}/transfer` er den eneste sync-i-async-risiko her, og den er allerede korrekt håndteret med `loop.run_in_executor(...)`.
