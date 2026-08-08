# Backend — Familieoverblik

FastAPI + uvicorn app. Single process, single async event loop. Runs on Windows (local dev) and in Termux on the tablet (production). Entry point: `backend/main.py`.

> **Status:** Living document, opdateres i takt med den systematiske code review. Dækker i dag: `main.py`, `check_deps.py`, `store.py`, `mqtt_client.py`, `aula_version.py`, `aula_client.py`, `aula_auth.py`, `cast_service.py`, `spotify_utils.py`, `google_utils.py`. Backend er nu fuldt gennemgået. Se `routers/CLAUDE.md` og `aula_lib/CLAUDE.md` for API-endpoints hhv. det vendored MitID-bibliotek.

## Kørselsmodel — vigtigt at forstå før du tilføjer kode

- **Globale singletons**, oprettet ved import af `main.py`: `client` (AulaClient), `aula_auth` (AulaAuth), `mqtt_client`. Der er kun én instans, delt af alle requests — ikke per-request. Det er en bevidst arkitektur for et single-user dashboard, ikke en fejl.
- **Sync `def`-routes køres automatisk i en trådpulje af Starlette** — de blokerer IKKE event loopet, selv med blokerende `requests`-kald indeni. De fleste Aula-endpoints (kalender, galleri, profil, klasser) er `def` og er derfor sikre som de er.
- **`async def`-routes og baggrundstasks er IKKE automatisk trådpuljede.** Hvis sådan en kalder blokerende kode direkte, fryser det *hele* serveren (cast, vejr, websockets, alt) for varigheden af kaldet. Wrap blokerende kald i `starlette.concurrency.run_in_threadpool`. Se `routers/aula.py::update_presence` og `main.py::_session_keepalive` for eksemplet — begge blev rettet for præcis dette.
- **Startup-sekvens** (`main.py`): `check_deps` → mDNS-registrering → sikr default `.env`-nøgler → app + routers → baggrundstasks (mqtt connect, cast start, `_session_keepalive` loop, `_google_calendar_sync` loop, `auto_refresh_loop`, `_ugebrev_sync_loop`, `_startup_token_refresh`).

## Driftsstabilitet — "hvorfor stopper serveren nogle gange?"

Undersøgt august 2026 efter gentagne rapporter om at serveren "bare stopper" og skal genstartes manuelt. Tre reelle, uafhængige årsager fundet — ingen af dem er en enkelt "smoking gun", alle bidrager:

1. **`install.sh`'s deploy-trin manglede en genstarts-watchdog** (rettet) — Termux:Boot-scriptet havde altid en `while true`-løkke der genstarter uvicorn ved crash, men det almindelige "kør install.sh for at opdatere"-trin startede blot serveren ÉN gang uden nogen watchdog. Et crash mellem to deploys efterlod derfor serveren nede indtil enten en manuel genstart eller en fysisk genstart af tabletten. Løsningen: begge veje deler nu `scripts/run_server.sh`, som ALTID genstarter ved crash — se scriptets kommentarer.
2. **`aula_auth.py::auto_refresh_loop()` manglede try/except om løkkens krop** (rettet) — modsat de tre tilsvarende loops i `main.py`. Én uventet fejl (korrupt `tokens.json`, en netværks-timeout `_try_refresh()` ikke selv fangede) ville stille dræbe HELE token-fornyelsen permanent — serverprocessen kører videre og ser "oppe" ud, men Aula-sessionen udløber til sidst og fornys aldrig igen. Udadtil ligner det "serveren er stoppet", uden noget synligt nedbrud at fejlfinde på. Testet: injiceret en fejl i loop-kroppen, bekræftet at loopet nu overlever og fortsætter (ramte 5 iterationer i test, mod 1 før rettelsen).
3. **Global asyncio exception-handler tilføjet i `startup()`** (`loop.set_exception_handler(...)`) som et sikkerhedsnet mod PRÆCIS samme fejlklasse i fremtidige, endnu-uopdagede baggrundstasks — en `asyncio.create_task()`-task der fejler uventet dør ellers helt lydløst (kun en svær-at-få-øje-på "Task exception was never retrieved" i loggen). Nu logges enhver sådan fejl højlydt med fuld traceback. Testet isoleret (uafhængigt af FastAPI/TestClient's egen loop-håndtering, som viste sig upålidelig til denne slags test).

**Ikke rettet, kan ikke rettes i Python-kode — kræver en Android-indstilling:** Termux kører i baggrunden (Fully Kiosk er den synlige/forgrunds-app), og Android kan derfor lukke HELE Termux-processen ved batterioptimering/OOM-pres, uafhængigt af alt ovenstående — ingen watchdog inde i processen kan overleve at selve processen bliver dræbt udefra. `install.sh` printer nu en påmindelse om dette ved hver installation: *Indstillinger → Apps → Termux → Batteri → "Ingen begrænsninger"*, evt. suppleret med `termux-wake-lock`. Hvis crashes fortsætter efter ovenstående rettelser, er dette den mest sandsynlige resterende årsag — tjek `server.log`s genstarts-tidsstempler (nu inkl. exit code, se `run_server.sh`) op mod hvornår skærmen har været slukket/enheden inaktiv, for at bekræfte mistanken.

## `ugebrev.py` — skoleskema fra "ugebrev" til kalenderen

**"Ugebrev" er i praksis observeret som et Aula ****opslag**** ("Opslag", delt med hele klassen via `posts.getAllPosts`), IKKE en privat besked.** Modulet blev oprindeligt bygget udelukkende omkring beskedtråde — helt fejlfrit kode, men mod den forkerte datamodel, så featuren aldrig fandt noget indhold i praksis.

**Ingen manuel indstilling — altid aktiv, barnet bestemmes automatisk.** Der er bevidst hverken en "aktivér"-knap eller et "vælg barn"-felt i settings.html. `_find_calendar_tag_for_doc(client, doc_url)` finder hvilket barn et opslag med en given URL faktisk blev delt til, ved at forespørge Aula PR. BARN (`client.get_posts([child_id], ...)` — samme opdeling Aula selv bruger) og se hvis barns opslagsliste indeholder linket. Det undgår at skulle kende/stole på et internt Aula-felt for "hvilken klasse/gruppe et opslag hører til", som ikke er bekræftet at eksistere i den offentlige respons. `_get_children(client)` henter børnelisten fra `client.get_profile()`.

- **Kerne-funktionen `_sync_core(client, calendar_tag, doc_url, anchor_date)` er bevidst kilde-uafhængig** — tager imod en allerede-bestemt kalender-tag + URL i stedet for selv at slå noget op. Både `sync_ugebrev_url()` (bruger-klik) og `sync_ugebrev()` (automatisk scanning) deler den uden at duplikere hente/parse/gem-logik.
- **`sync_ugebrev_url(client, doc_url, anchor_date_str)`** — ingen barn-parameter — er den variant frontend kalder direkte fra "🎒 Tilføj til skolekalender"-knappen i **både** `aula.js`s besked-modal og `calendar.js`s opslags-modal (`openPost()`). Frontend udtrækker selv doc_url fra det indhold der allerede vises; backend bestemmer selv barnet via `_find_calendar_tag_for_doc`. Fejler pænt med en forklarende besked hvis linket ikke findes i nogen af børnenes seneste 15 opslag (fx hvis det reelt var en besked, ikke et opslag).
- **`sync_ugebrev(client)`** — heller ingen parametre — er baggrundsscanneren (hver 6. time, `_ugebrev_sync_loop` i `main.py`) og "Synkroniser nu"-knappen i settings.html. Looper over ALLE børn, tjekker hver enkelts seneste opslag, og synkroniserer hvert barn med et matchende Google Docs-link til sin egen kalender — håndterer flere børn i forskellige klasser uden videre. Returnerer `{"found": False, "message": ...}` eller `{"found": True, "results": [{"child_name":.., "week":.., "events_created":..}, ...]}` — **bemærk listeformen**, det er IKKE samme flade shape som `sync_ugebrev_url()` returnerer, fordi flere børn kan matche i samme kørsel. Frontend/endpoint-kode der læser resultatet skal kende forskel på de to (se `/api/ugebrev/sync` vs. `/api/ugebrev/sync-url` i `main.py`).
- **Brødtekst-udtræk**: `parse_schedule()` inkluderer nu `"body_text"` — al paragraf-/overskriftstekst UDENFOR selve skematabellen (typisk lærerens ugentlige huskere, som skematabellen ikke har plads til). Gemmes separat via `store.save_ugebrev_note()` (nøgle `"{calendar_tag}|{year}|{week}"`, egen lille JSON-fil `ugebrev_notes.json`, IKKE en del af `custom_events.json` — det er ikke et kalenderevent). Hentes af `GET /api/ugebrev/info` til info-ikonet i `frontend/js/skolekalender.js`. Ekskluderer korrekt tabelcelle-tekst via `tag.find_parent("table") is table`-tjek — test dette specifikt hvis du ændrer parsingen, en fejl her ville lade skematabellens indhold "lække" ind i brødteksten.
- **Ugenummer læses fra dokumentets tekst** ("Uge XX"), ikke fra opslagsdatoen — men den dato bruges som "anker" til at vælge det rigtige ÅR for det ugenummer (`resolve_week_dates`), fordi et ugenummer alene er tvetydigt over årsskiftet (uge 1 delt i december hører til næste år). Testet med begge retninger af årsskifte-tvivlen.
- **Kildetabellens tidskolonne kan skrive et interval** (`"8.00-8.45"`, `"8-8.45"`, eller med en Unicode-dash i stedet for almindelig bindestreg — Google Docs' autokorrektur bytter den nogle gange ud) — `_parse_time()` tager kun imod starten af intervallet, og en bar time uden minutter ("8") tolkes som hele timen ("08:00"). Uden dette parses hele rækken som ugyldig og forsvinder stille, hvilket i praksis fjernede en hel dags eneste indhold.
- **Dag-headers matches uafhængigt af versaler/kolon** ("MANDAG", "mandag:", "Mandag" giver alle "Mandag") — kildedokumentets skrivemåde varierer i praksis mellem klasser/skoler.
- **Dubletter af samme dagnavn i header-rækken** (set i praksis — to "Fredag"-kolonner i kildedokumentet) kollapses til FØRSTE forekomst. Ingen automatisk lige/ulige-uge-logik — der var ikke belæg for at gætte på hvorfor duplikaten fandtes.
- **Ikon-mapping (`ICON_KEYWORDS`) er nøgleord → emoji, rækkefølge betyder noget** — mere specifikke ord skal stå højere end generiske for at undgå fejlmatch (fx "lege" som delstreng af "leger" matchede før "morgenbånd" blev tjekket, indtil ordren blev rettet). Test nye nøgleord mod eksisterende titler, ikke kun isoleret.
- **Idempotent via `(calendar_tag, week, year)` som naturlig nøgle**, ikke tråd-/opslags-id — en gentaget/rettet sync for samme uge overskriver kun præcis den uges auto-genererede events, aldrig andre ugers eller manuelt oprettede events. Se `replace_ugebrev_events()`.
- **Events tagges med `calendar: "cal-child-<id>"`** — samme konvention som når man manuelt opretter et event og vælger et barn (se `frontend/js/CLAUDE.md`). Ingen særskilt "hvilket barn"-logik nødvendig i frontend — events flyder gennem den eksisterende `googleEvents`/custom-events-pipeline.
- **Titel-format er ALTID `"{ikon} {tekst}"`** (ét emoji, ét mellemrum, resten) — `frontend/js/skolekalender.js` splitter på det første mellemrum for at vise ikon og tekst separat. Ændrer du formatet her, skal den opdateres samtidig.
- **`AulaClient`s metode hedder `get_messages_for_thread(thread_id, page=0)`, IKKE `get_messages(thread_id)`** — sidstnævnte findes slet ikke og fejler med `AttributeError`. Denne fejl lå upåagtet i koden fra featurens første version, fordi ingen af de tidligere tests rent faktisk mockede/kaldte `client`-metoden direkte (kun UI-routing og isoleret parsing blev testet). Skriv altid en test der mocker `client`s metoder direkte og går gennem den rigtige funktion/endpoint, ikke kun parsing-funktionerne isoleret.
- **Hele kæden er verificeret mod et rigtigt, live Google Docs-dokument** (ikke kun mocket) via en Playwright-test der genskabte den faktiske post-struktur og klikkede den rigtige knap — 30 events for den rigtige uge blev korrekt oprettet, derefter ryddet op igen. Foretræk denne slags "hele vejen igennem, mod ægte ekstern data"-test frem for udelukkende mocks når muligt for netop denne feature — den har haft flere fejl som kun ægte data afslørede (forkert Aula-datamodel, forkert clientmetode).
## `/api/file-proxy` (i `main.py`) — vigtig gotcha

Streamer en Aula-fil videre via `client.session.get(url, stream=True)` + `r.iter_content()`. **Forward ALDRIG origin'ens `Content-Length`-header** — `iter_content()` afkomprimerer transparent gzip/deflate-indhold, så det oprindelige (komprimerede) `Content-Length` ikke længere matcher de bytes vi reelt sender. Browseren klipper downloadet ved den forkerte, korte længde (set i praksis: PDF-titel/første bytes kom med, resten ikke — filen fremstod som "kan ikke åbnes"). Lad Starlette bruge chunked transfer-encoding i stedet ved simpelthen ikke at sætte headeren. Samme faldgrube gælder principielt `/api/profile-picture`, som dog ikke forwarder Content-Length i dag — rør ikke ved det uden at huske denne note.

## `check_deps.py`

Tjekker at alle Python-pakker er installeret *før* appen starter — fejler hurtigt med en klar `pip install`/`pkg install`-besked i stedet for en kryptisk `ImportError` midt i et request. **Tilføj nye dependencies her**, når du tilføjer en ny integration.

## `NoCacheMiddleware` (i `main.py`)

Sætter `Cache-Control: no-store` på en eksplicit liste af paths — kun `/`, `/index.html` og `/settings.html` i dag. **Enhver ny HTML-side der tilføjes til frontend/, og som brugeren navigerer direkte til (ikke kun loades via fetch), skal føjes til denne liste**, ellers kan browseren/Fully Kiosk cache en gammel version efter et deploy uden at nogen opdager det — nøjagtig det der skete med `/settings.html` før den blev tilføjet (en helt ny indstillings-sektion var usynlig for brugeren i lang tid, ikke fordi koden var forkert, men fordi siden aldrig blev hentet frisk).

## `store.py`

JSON-fil-storage for custom (manuelt tilføjede) kalenderevents, med `threading.Lock` for skrive-sikkerhed. Ved læsefejl logges en advarsel og der returneres `[]` — filen bliver IKKE overskrevet, så data er ikke tabt, bare skjult indtil fejlen er rettet. Se logs for `store`-advarsler hvis custom events pludselig forsvinder.

- **`load_ugebrev_notes()`/`save_ugebrev_note()`** er en separat lille JSON-fil (`ugebrev_notes.json`, egen lock) til ugebrevets brødtekst — bevidst IKKE en del af `custom_events.json`, da det ikke er et kalenderevent. Nøgle: `"{calendar_tag}|{year}|{week}"`.

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
- **`auto_refresh_loop()`s løkke-krop er nu i et try/except** (var det ikke tidligere — se "Driftsstabilitet"-sektionen øverst i denne fil for hvorfor det var et reelt, ikke-hypotetisk problem).
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
