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

## `ugebrev.py` — skoleskema/SFO-ugeplan fra Aula-opslag til kalenderen

**Genkendelse sker på opslagets TITEL, ikke på indholdet.** `_is_weekly_letter_post(title)` matcher "ugebrev"/"ugeplan" (case-insensitive) — dækker alle observerede varianter ("Ugebrev 35", "Ugebrev uge 34 (og 35)", "Ugeplan uge 35", "SFO ugeplan..."). `_weeks_from_title(title)` udtrækker simpelthen ALLE tal i titlen (ikke en snæver "uge \d+"-regex) — en titel har i praksis aldrig andre tal end ugenumre, og dette dækker både "Ugebrev uge 34" og det bare "Ugebrev 35"-format uden ordet "uge". Dette erstattede en tidligere tilgang der lagde ugenummeret ind i selve Google Docs-dokumentets overskrifter (`split_document_into_weeks`/`SECTION_HEADING_RE`, stadig brugt internt til at PARSE et fundet dokument — se nedenfor) — den gamle tilgang fejlede i praksis når skolen skrev overskriften på en måde regex'en ikke fangede, hvorved flere ugers indhold kollapsede sammen under én uge-nøgle (det oprindelige "jeg får info fra alle ugerne"-bugrapport, august 2026).

**Barnet/børnene bestemmes via Aulas EGET `sharedWithGroups`-felt** (`_own_children_for_post`), ikke ved at gætte ud fra dokumentindhold. To trin:
1. Hurtig sti — slå gruppen op i `client.get_groups_cached()` (id ELLER navn — navnematch er en fallback for det tilfælde IDs skifter mellem endpoints). Denne cache indeholder kun grupper med `membershipType == "direct"` (klasser).
2. Falder tilbage til `client.get_group_member_ids(group_id)` (nyt, se `aula_client.py`-sektionen) for grupper der IKKE er "direct" — set i praksis: en SFO-ugeplan delt med en tværklasse-"årgang"-gruppe. Hvis gruppens medlemmer er BØRN, matches direkte mod egne børns institutionProfileId. Hvis gruppen i stedet er en GUARDIAN-niveau-gruppe (fx "0. årgang forældre" — medlemslisten er forældreprofiler, ikke børn), tjekkes om VI selv (`client._get_guardian_profile_ids()`) er medlem, og opslaget antages da at gælde ALLE egne børn (kan ikke skelnes yderligere ud fra medlemskabet alene).

`_find_calendar_tag_for_doc(client, doc_url)` (den GAMLE reverse-lookup-metode — forespørger Aula pr. barn og ser om barnets opslagsliste indeholder et matchende dokument-link) lever videre, men bruges KUN af `sync_ugebrev_url()` (den manuelle "🎒 Tilføj til skolekalender"-knap, som kun har en doc_url at gå ud fra, intet post-objekt med `sharedWithGroups`).

**Tre grene pr. (opslag, barn) i `sync_ugebrev()`, forsøgt i rækkefølge — første der giver indhold vinder:**
1. **Google Docs-link MED en brugbar tabel** — `parse_document()`/`_parse_table()` (uændret tabel-parsing-logik, se detaljer nedenfor), men resultatet filtreres til KUN de uger titlen faktisk nævner (hvis titlen nævner nogen — ellers bruges alle uger fundet i dokumentet, bagudkompatibel adfærd for et dokument uden ugenummer i titlen).
2. **Et billede** (`_post_image_urls()` finder vedhæftningens fulde billed-URL) — `_ocr_parse_weekplan_image()` læser det LOKALT via Tesseract (`pytesseract`), INGEN AI-API, ingen netværkskald ud over selve billed-hentningen. Finder ugedags-overskrifternes x-position i billedet for at etablere kolonner, tildeler dernæst kolonne **PR. ORD** (ikke pr. Tesseract-"linje" — Tesseracts egen linjegruppering kan i praksis spænde på tværs af flere fysiske kolonner i en tabel uden cellekanter, hvilket blev observeret at slå flere dages indhold sammen til én garbled streng), og klynger derefter selv ordene til rækker/aktiviteter ud fra vertikal nærhed (median ordhøjde som skala) — dette gør at en aktivitet skrevet over flere linjer (fx "Mountainbike med" / "Kevin") samles til ÉT kalenderpunkt, mens to reelt forskellige aktiviteter i samme celle (adskilt af et klip-art-billede, større afstand) forbliver separate. Sætter `is_sfo=True` hvis ordet "SFO" optræder i billedet — SFO-events får egen farve (`SFO_EVENT_COLOR`) og `source: "sfo_ugebrev"` (mod almindeligt `"ugebrev_billede"`), så de kan skelnes visuelt og aldrig overskriver skolens eget tabel-skema for samme uge.
3. **Hverken tabel eller billede** — selve opslagsteksten (`BeautifulSoup(html).get_text()`) gemmes direkte som ugebrev-note (samme sted info-ikonet henter fra). Dækker et rent tekst-ugebrev uden skema (set i praksis: en 0.-klasses ugebrev der kun er løbende prosa).

**`_should_resync()` — kun manglende uger, eller den nærmeste, gensynkroniseres hver kørsel** (ikke hele dokumentets/historikkens uger hver gang, som den oprindelige implementering gjorde — kostbart og unødvendigt, andet oprindeligt bugpunkt). "Nærmeste" = ugens mandag er inden for ±10 dage af i dag; sådanne uger gensynkroniseres ALTID (skolen retter ofte den kommende uge), ældre uger kun hvis de mangler helt.

**Posts sorteres ÆLDST-FØRST før behandling** (`sorted(posts, key=lambda p: p.get("timestamp") or "")`) — Aula returnerer nyeste-først, men skoler sender ofte overlappende "kombi-ugebreve" (fx "uge 33 (og 34)" efterfulgt senere af "uge 34 (og 35)"), som begge rører samme uge. Ved at behandle ældste post først, og lade "sidste skriv vinder" (samme (calendar_tag, uge, år)-nøgle overskrives), ender en delt uge deterministisk med det NYESTE opslags version, i stedet for at det afhænger tilfældigt af feed-rækkefølgen. Uden denne sortering kunne en ældre posts indhold overskrive en nyere posts indhold for samme uge (fundet ved live-test august 2026).

**Ugenummer/år-opløsning (`resolve_week_dates`, uændret)**: bruger opslagets tidsstempel som "anker" til at vælge det rigtige ÅR for et ugenummer — tvetydigt over årsskiftet (uge 1 nævnt i december hører til næste år).

**Bevidst IKKE ændret — stadig brugt af `sync_ugebrev_url()`/`_sync_core()` (den manuelle knap-flow) og af selve tabel-parsingen i gren 1 ovenfor:**
- `split_document_into_weeks()`/`SECTION_HEADING_RE` — splitter ét dokument der akkumulerer mange uger (skolen genbruger ét løbende Google Doc for hele skoleåret) i sektioner ved "Uge XX"-overskrifter.
- `_parse_table()` — dag-headers matches uafhængigt af versaler/kolon, `DAY_ABBREVIATIONS` accepterer forkortelser ("Man"/"Tirs"/osv.), dubletter af samme dagnavn kollapses til første forekomst, `_parse_time_range()` respekterer et eksplicit sluttidspunkt i en celle frem for altid at udlede det af næste rækkes start.
- `ICON_KEYWORDS` — nøgleord → emoji, rækkefølge betyder noget (mere specifikke ord højere end generiske).
- Idempotent via `(calendar_tag, week, year, source)` som nøgle, se `replace_ugebrev_events()` — nu med et `source`-parameter (`"ugebrev"`/`"sfo_ugebrev"`/`"ugebrev_billede"`) så en billed-baseret sync for en uge ikke sletter en tabel-baseret sync for SAMME uge, og omvendt.
- Titel-format `"{ikon} {tekst}"` — `frontend/js/skolekalender.js` splitter på det første mellemrum.
- `AulaClient`s metode hedder `get_messages_for_thread(thread_id, page=0)`, IKKE `get_messages(thread_id)`.

**Bevidst IKKE forsøgt endnu**: OCR af håndskrevne ugeplaner (Tesseract er trænet til trykt tekst), datakilder ud over Google Docs/billeder (Sheets, PDF).

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
- **`get_groups()` (Klasser-fanen):** Filtrerer børn fra voksne via en **blocklist af voksenroller** (`guardian`, `teacher`, `pedagogue`, `employee`, `leader`, `other`) — bevidst valgt over en whitelist af børneroller, fordi Aula introducerer nye rollenavne per klassetrin uden varsel (`"early-student"` for 0. klasse dukkede op uden varsel i august 2026 og fik alle klasser til at vise 0 børn). Skriver til `groups_cache.json` som fallback — men **kun hvis resultatet ikke er tomt**, så en forbigående fejl ikke sletter en god cache. `get_groups_cached()` falder også tilbage til disk-cachen hvis `get_groups()` returnerer tomt uden at kaste en exception. **Medtager KUN grupper med `membershipType == "direct"`** (klasser/hovedgrupper) — bevidst afgrænset til det kontaktlisten faktisk skal bruge.
- **`get_group_member_ids(group_id)`** (nyt) — modsat `get_groups()` ovenfor filtrerer denne INTET på membershipType; kalder `groups.getMemberships` direkte for ét vilkårligt gruppe-id og returnerer alle institutionProfileId'er som et sæt. Bruges af `backend/ugebrev.py::_own_children_for_post` til at slå tværklasse-grupper op (fx "0. årgang forældre"), som `get_groups()` bevidst ikke overvåger. **Kan 403'e for en gruppe man ikke selv er portalRole-berettiget til** (fx en "medarbejdere"-gruppe, når man kun er guardian) — det er forventet og fanges/logges, ikke en fejl at rette.
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
