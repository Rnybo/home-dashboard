# frontend/js/ — Client-side app

> **Status:** Living document. Dækker i dag app-skallen: `globals.js`, `app.js`, `auth.js`, `utils.js`, `cache.js`, `family.js`, `calendar.js`, `klasse.js`. Ikke dækket endnu: `gallery.js`, `aula.js`, `cast.js`, `presence_edit.js` (feature-moduler). Se `js/apps/CLAUDE.md` for børnenes spil.

Ingen build-step, ingen moduler — rå `<script src>`-tags indlæst i rækkefølge fra `index.html`. **Rækkefølgen er kritisk**, fordi senere filer kan overskrive tidligere `function`-deklarationer med samme navn i det globale scope:

```
cache.js → globals.js → presence_edit.js → calendar.js → klasse.js → gallery.js
→ aula.js → auth.js → utils.js → cast.js → family.js → apps/*.js → app.js
```

**Skriv aldrig to funktioner med samme navn i to forskellige filer.** Det sker uden fejl eller advarsel — den sidst indlæste fil vinder stille. Dette skete faktisk: `loadWeather()`, `loadGoogleCalendar()` og `loadProfileConfig()` lå duplikeret i både `globals.js` og `utils.js` (som loader senere), så `utils.js`'s simplere, ikke-cachede versioner overskrev de rigtige uden at nogen opdagede det. `utils.js` er nu tømt for indhold (kun en kommentar) — filen skal stadig eksistere som separat `<script>`-tag for load-rækkefølgens skyld, men bør ikke få nyt indhold uden at tjekke grundigt for navnekollisioner med `globals.js`.

## `cache.js` — localStorage-cache til API-data

`cacheFetch(key, fetchFn, onData, sessionValid)`: viser cached data **øjeblikkeligt** (uanset alder), henter derefter friske data i baggrunden og opdaterer UI'et igen når de ankommer. `sessionValid=false` (Aula-session udløbet) → viser **kun** cache, forsøger ikke live-hentning. `CACHE_TTL` styrer kun hvornår baggrunds-refresh anses for nødvendig — cache vises altid uanset TTL.

**Brug `cacheFetch()` for alt nyt der henter Aula/eksternt data** — det er det som gør dashboardet robust over for kortvarige netværksudsving (ser stadig sidste kendte data i stedet for en tom skærm).

## `globals.js` — state, config, delte helpers

- **`initConfig()` henter `/api/config` (giver `API_KEY`) — retryer nu i det uendelige med backoff** hvis kaldet fejler, og viser en synlig fejl i header-titlen. Uden `API_KEY` fejler *alt* andet API-kald med 403 — gjorde tidligere kun 2 forsøg og gav derefter permanent, usynligt op.
- **`apiFetch()`** er standard-wrapperen for alle API-kald — tilføjer `x-api-key`-header, kaster en fejl med `.status` sat på 401/403 (fanges af `cacheFetch` til at vise login-banner).
- `switchView()`'s dropdown-aktiv-tilstand bruger `data-view`-attributter på `.aula-dd-item`-elementerne (i `index.html`) — brugte tidligere regex på `onclick`-strengen, hvilket fejlede stille for viewnavne med bindestreg (`family-kids`/`family-adults` fik aldrig sat aktiv-klassen korrekt, da `\w` ikke matcher `-`).

## `calendar.js` — ugevisning, "i dag"-widget, event-info-modal

- **`renderTodayWidget()` bygger nu hvert kort (barn + "Familien") færdigt i ét hug** inklusiv rute-rækker — erstattede en tidligere version der byggede hele HTML-strengen først og bagefter brugte et regex find/erstat til at sprøjte rute-data ind i det allerede-byggede resultat. Skrøbeligt (afhang af at børnenavne matchede en dynamisk bygget regex) og svært at følge; byg nyt indhold direkte, aldrig via post-hoc regex på egen genereret HTML.
- **`_addMinutes(timeStr, mins)`** er en lille hjælper til "HH:MM + N minutter"-aritmetik (bruges til presence-bar'ens visuelle sluttidspunkt) — brug den frem for at genopfinde tidsregning inline.
- `openPost()` finder post-elementet via `data-postid` (ikke `onclick`-streng-match).
- `_renderWeekNow()` viser nu "📅 Indlæser kalender…" hvis `CHILDREN` endnu ikke er indlæst, i stedet for at vise et helt tomt kalenderområde.
- PIN-koden til børnelåsen (`clHash()`) bruger en bevidst simpel, ikke-kryptografisk hash — det er en friktionsmekanisme mod nysgerrige børn, ikke en sikkerhedsgrænse. Skift den ikke til noget "stærkere" uden grund; det løser intet reelt problem her.

## `klasse.js` — klasseoversigt, kontaktinfo, fødselsdage

- Cacher grupper og kontaktinfo direkte i `localStorage` (`ls_groups`, `ls_contacts_<groupId>`) — et separat, simplere mønster end `cache.js`'s `cacheFetch()` (ingen TTL, viser altid cache først uanset alder). Fungerer fint, men vær opmærksom på at det er en anden caching-tilgang end resten af appen hvis du reviderer det.
- **`.klasse-child-row` har et `data-child-id`-attribut** — brug det til at finde et barns række/ID fra DOM'en. Brugte tidligere regex på `onclick`-attributten (samme mønster som blev rettet i `calendar.js`/`globals.js`).
- `renderContactPanel()` viser kun kontaktinfo forældre selv har givet samtykke til at dele (`userHasGivenConsentToShowContactInformation`) — filtreres allerede server-side i `aula_client.py::get_contact_list()`, denne fil viser bare det den får.

## `app.js` — kalendervisning, event-modal, boot-sekvens

- **`loadAll()`** er hoved-boot-funktionen: first-run check → `initConfig()` → `checkSession()` → load alt parallelt (kalender, presence, beskeder, overview, google, vejr, ruter) → `schedulePoll(15 min)`.
- **`saveEventLocal()` og "Fjern fra kalender"-knapperne tjekker nu faktisk om requestet lykkedes** før de viser succes/lukker dialogen. De gjorde det ikke tidligere — en fejlet gem/slet blev vist som succes, hvilket er værre end en fejlbesked (brugeren tror handlingen virkede og opdager først senere at den ikke gjorde).
- `layoutEvents()` håndterer overlappende kalenderbegivenheder (side-om-side kolonner) — ret kompleks kolonne-tildelingsalgoritme, test grundigt hvis den ændres.
- Event-titel/beskrivelse escapes manuelt med regex (`.replace(/"/g,'&quot;')`) før indsættelse i HTML-attributter — dækker kun anførselstegn, ikke `<`/`>`. Lavrisiko (data kommer fra Aula/Google, ikke direkte brugerinput), men værd at være opmærksom på hvis en begivenhedstitel nogensinde indeholder specialtegn.

## `auth.js` — MitID login-UI + session-status

Håndterer login-dropdown, konto-skift, og MitID QR-kode-flowet (polling `/api/login/status` hvert sekund, animeret QR mellem to frames). God, tydelig state-maskine (`idle`/`running`/`show_qr`/`success`/`failed`). Ingen timeout på selve pollingen — hænger den i `running` for evigt, poller den for evigt uden at foreslå brugeren at prøve igen.

## `family.js` — Familie-app-grid og bund-navigation

Statisk `FAMILY_APPS`-konfiguration (kids/adults), aktiveres via Indstillinger (`localStorage` `family_kids_apps`/`family_adults_apps`). `shuffle()` her er delt af regnespil og huskespil.
