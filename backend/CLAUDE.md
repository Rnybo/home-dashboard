# Backend — Familieoverblik

FastAPI + uvicorn app. Single process, single async event loop. Runs on Windows (local dev) and in Termux on the tablet (production). Entry point: `backend/main.py`.

> **Status:** Living document, opdateres i takt med den systematiske code review. Dækker i dag: `main.py`, `check_deps.py`, `store.py`, `mqtt_client.py`, `aula_version.py`, `aula_client.py`, `aula_auth.py`, `cast_service.py`, `spotify_utils.py`, `google_utils.py`. Backend er nu fuldt gennemgået. Se `routers/CLAUDE.md` og `aula_lib/CLAUDE.md` for API-endpoints hhv. det vendored MitID-bibliotek.

## Kørselsmodel — vigtigt at forstå før du tilføjer kode

- **Globale singletons**, oprettet ved import af `main.py`: `client` (AulaClient), `aula_auth` (AulaAuth), `mqtt_client`. Der er kun én instans, delt af alle requests — ikke per-request. Det er en bevidst arkitektur for et single-user dashboard, ikke en fejl.
- **Sync `def`-routes køres automatisk i en trådpulje af Starlette** — de blokerer IKKE event loopet, selv med blokerende `requests`-kald indeni. De fleste Aula-endpoints (kalender, galleri, profil, klasser) er `def` og er derfor sikre som de er.
- **`async def`-routes og baggrundstasks er IKKE automatisk trådpuljede.** Hvis sådan en kalder blokerende kode direkte, fryser det *hele* serveren (cast, vejr, websockets, alt) for varigheden af kaldet. Wrap blokerende kald i `starlette.concurrency.run_in_threadpool`. Se `routers/aula.py::update_presence` og `main.py::_session_keepalive` for eksemplet — begge blev rettet for præcis dette.
- **Startup-sekvens** (`main.py`): `check_deps` → mDNS-registrering → sikr default `.env`-nøgler → app + routers → baggrundstasks (mqtt connect, cast start, `_session_keepalive` loop, `_google_calendar_sync` loop, `auto_refresh_loop`, `_startup_token_refresh`).

## `/api/file-proxy` (i `main.py`) — vigtig gotcha

Streamer en Aula-fil videre via `client.session.get(url, stream=True)` + `r.iter_content()`. **Forward ALDRIG origin'ens `Content-Length`-header** — `iter_content()` afkomprimerer transparent gzip/deflate-indhold, så det oprindelige (komprimerede) `Content-Length` ikke længere matcher de bytes vi reelt sender. Browseren klipper downloadet ved den forkerte, korte længde (set i praksis: PDF-titel/første bytes kom med, resten ikke — filen fremstod som "kan ikke åbnes"). Lad Starlette bruge chunked transfer-encoding i stedet ved simpelthen ikke at sætte headeren. Samme faldgrube gælder principielt `/api/profile-picture`, som dog ikke forwarder Content-Length i dag — rør ikke ved det uden at huske denne note.

## `check_deps.py`

Tjekker at alle Python-pakker er installeret *før* appen starter — fejler hurtigt med en klar `pip install`/`pkg install`-besked i stedet for en kryptisk `ImportError` midt i et request. **Tilføj nye dependencies her**, når du tilføjer en ny integration.

## `store.py`

JSON-fil-storage for custom (manuelt tilføjede) kalenderevents, med `threading.Lock` for skrive-sikkerhed. Ved læsefejl logges en advarsel og der returneres `[]` — filen bliver IKKE overskrevet, så data er ikke tabt, bare skjult indtil fejlen er rettet. Se logs for `store`-advarsler hvis custom events pludselig forsvinder.

## `mqtt_client.py`

Singleton omkring paho-mqtt, publiserer til lokal Mosquitto (`localhost:1883`) — bruges til at broadcaste intern state (session-gyldighed, cast-state, event-sync) til andre dele af appen. Designet til **aldrig** at kunne crashe serveren — alle paho-kald er i try/except.

- Watchdog-tråd genforbinder hvert 15. sekund hvis forbindelsen tabes.
- **`_NO_RETRY_RC = {4, 5}`** — kun disse betyder permanent auth-fejl (deaktiverer klienten permanent, med vilje, for ikke at spamme logs). **Rør ikke ved denne liste uden at bekræfte at en ny kode faktisk er en permanent auth-fejl** — rc=7 blev fejlagtigt inkluderet her tidligere (det er paho's `MQTT_ERR_CONN_LOST`, en helt normal netværksfejl), hvilket kunne deaktivere MQTT permanent efter en almindelig forbindelsesudsving.

## `aula_version.py`

Aula lukker jævnligt deres API-version ned (returnerer `HTTP 410 Gone` på *alt*, uden varsel) og skifter til en ny. Dette modul husker den nuværende kendte version i `api_version.json` (repo-rod, gitignored — det er runtime-state, ikke kode) og bumper + retryer automatisk (op til 5 gange) når et 410 ses.

**Alle Aula HTTP-kald skal gå gennem `aula_version.get()` / `.post()` / `.async_get()`** i stedet for at ramme `https://www.aula.dk/api/v{N}/` direkte — så fremtidige versionsskift selvheler i stedet for at kræve en manuel kodefix (som skete i maj/august 2026).

## `aula_client.py` — session state og Aula-data

`AulaClient` er den globale, delte klient (`client` i `main.py`) der holder på session-cookies og henter alt Aula-data (kalender, galleri, klasser, beskeder, tilstedeværelse).

- **Session lever i `session.json`** (repo-rod, gitignored) og indeholder kun `PHPSESSID` + `CSRF_TOKEN`. Cookies sættes med **`domain=".aula.dk"`** — samme domæne som Aula selv bruger til at rotere `PHPSESSID`. Hvis du nogensinde ændrer `_apply_credentials()`, bevar det domæne — uden det får du to konkurrerende `PHPSESSID`-cookies i samme jar og sporadiske 403'ere (skete i august 2026, kostede en hel debugging-session).
- **`check_session()`** er *the* autoritet på om sessionen er gyldig — kalder `profiles.getProfileContext`, ikke `profiles.getProfilesByLogin` (den sidste returnerer 200 selv på ugyldige sessioner — brug den aldrig til validering).
- **`_get()`/`_post()`** er de fælles indgange for alle almindelige Aula-kald — de sætter `session_valid=False` og kaster `PermissionError` på 401/403. Nye metoder bør altid gå gennem disse, aldrig bygge deres eget request uden samme fejlhåndtering.
- **`get_groups()` (Klasser-fanen):** Filtrerer børn fra voksne via en **blocklist af voksenroller** (`guardian`, `teacher`, `pedagogue`, `employee`, `leader`, `other`) — bevidst valgt over en whitelist af børneroller, fordi Aula introducerer nye rollenavne per klassetrin uden varsel (`"early-student"` for 0. klasse dukkede op uden varsel i august 2026 og fik alle klasser til at vise 0 børn). Skriver til `groups_cache.json` som fallback — men **kun hvis resultatet ikke er tomt**, så en forbigående fejl ikke sletter en god cache. `get_groups_cached()` falder også tilbage til disk-cachen hvis `get_groups()` returnerer tomt uden at kaste en exception.
- **`_pic_url()`** bygger stabile billed-URLs fra Aulas `profilePicture.key` — strip altid filtypen før du tilføjer størrelsessuffiks (`_200x200.jpg`).

## `aula_auth.py` — MitID-login og token-refresh

Bruger `nickknissen/aula`-biblioteket (`aula_lib/`) til OAuth2 PKCE + SAML/MitID QR-flow. Ingen Playwright.

- **Tre steder kalder `_try_refresh()`** på samme `AulaAuth`-singleton: `_do_login()`, `_session_keepalive` i `main.py` (hvert 30. min), og `auto_refresh_loop` (hvert 50. min). **`_try_refresh()` er beskyttet af `self._refresh_lock` (asyncio.Lock)** og genindlæser `tokens.json` fra disk *efter* den har låsen — uden det kunne to samtidige refresh-kald bruge det samme allerede-brugte (roterende, single-use) refresh-token og korrumpere `tokens.json`. **Rør ikke ved denne lås uden at forstå racen.**
- **`_init_session_cookies()`** bruger `profiles.getProfilesByLogin` til at bytte et access_token til `PHPSESSID`/`Csrfp-Token` — virker fint til dette formål, ikke ændret uden grund.
- Alle Aula-HTTP-kald her går gennem `aula_version.async_get()`.

## `cast_service.py` — Chromecast/Nest device monitoring

mDNS-baseret Cast-device discovery + media-status monitoring, tydeligt modelleret efter Home Assistant's cast-integration (samme state-flags, samme edge-case-håndtering for upålidelige apps som Netflix). Publicerer state til MQTT ved ændring.

- **`_run()`'s discovery-loop genstarter automatisk** ved fejl (30 sek delay) og rydder `_chromecasts` i sin `finally`-blok — men rydder ikke `_state`, så `get_state()` kan returnere en anelse forældet data for enheder mellem en discovery-genstart og deres reconnect. Lav praktisk risiko, ikke rettet.
- **`transfer_playback()`** virker kun for direkte URL-streams (DR, radio) — **ikke Spotify**. Spotify kræver interne cookie-baserede credentials (`sp_dc`/`sp_key`) som ikke er tilgængelige via normal OAuth, så transfer for Spotify er bevidst ikke supporteret; brug Spotify-appen selv til enhedsskift.

## `spotify_utils.py`, `google_utils.py` — OAuth token-refresh

Begge følger samme mønster: in-memory token-cache + refresh via `refresh_token` fra `.env`. **`get_spotify_access_token()`/`_get_google_access_token()` fanger selv fejl fra refresh-kaldet og returnerer `""`** ved ugyldigt/tilbagekaldt refresh-token — kald dem altid som `if not token: <ikke forbundet>`, forvent aldrig at de kaster en exception. (De gjorde det tidligere ikke, hvilket gav rå 500'ere på fx `/api/google-oauth/calendars` når et token var udløbet.)

- **`_sync_google_event()`** (kaldt fra `routers/custom.py` i en baggrundstråd ved hvert custom-event) genbruger den globale `client`-singleton (via `from backend.main import client`) til at slå børns navne op — brug **ikke** `AulaClient()` direkte her, det opretter en overflødig instans og udløser et ekstra Aula-kald hver gang.

## Pending (not yet reviewed / documented here)

- Se `routers/CLAUDE.md` for API-endpoints
- `aula_lib/` (vendored bibliotek) kommer senere i reviewet
