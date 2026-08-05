# frontend/js/ — Client-side app

> **Status:** Living document. Dækker i dag app-skallen: `globals.js`, `app.js`, `auth.js`, `utils.js`, `cache.js`, `family.js`. Ikke dækket endnu: `calendar.js`, `klasse.js`, `gallery.js`, `aula.js`, `cast.js`, `presence_edit.js` (feature-moduler). Se `js/apps/CLAUDE.md` for børnenes spil.

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
- `switchView()`'s dropdown-aktiv-tilstand parser `onclick`-attributten med regex for at finde viewnavnet i stedet for et `data-view`-attribut — skrøbeligt, men ingen kendt aktiv bug. Overvej `data-view` hvis det skal udvides.

## `app.js` — kalendervisning, event-modal, boot-sekvens

- **`loadAll()`** er hoved-boot-funktionen: first-run check → `initConfig()` → `checkSession()` → load alt parallelt (kalender, presence, beskeder, overview, google, vejr, ruter) → `schedulePoll(15 min)`.
- **`saveEventLocal()` og "Fjern fra kalender"-knapperne tjekker nu faktisk om requestet lykkedes** før de viser succes/lukker dialogen. De gjorde det ikke tidligere — en fejlet gem/slet blev vist som succes, hvilket er værre end en fejlbesked (brugeren tror handlingen virkede og opdager først senere at den ikke gjorde).
- `layoutEvents()` håndterer overlappende kalenderbegivenheder (side-om-side kolonner) — ret kompleks kolonne-tildelingsalgoritme, test grundigt hvis den ændres.
- Event-titel/beskrivelse escapes manuelt med regex (`.replace(/"/g,'&quot;')`) før indsættelse i HTML-attributter — dækker kun anførselstegn, ikke `<`/`>`. Lavrisiko (data kommer fra Aula/Google, ikke direkte brugerinput), men værd at være opmærksom på hvis en begivenhedstitel nogensinde indeholder specialtegn.

## `auth.js` — MitID login-UI + session-status

Håndterer login-dropdown, konto-skift, og MitID QR-kode-flowet (polling `/api/login/status` hvert sekund, animeret QR mellem to frames). God, tydelig state-maskine (`idle`/`running`/`show_qr`/`success`/`failed`). Ingen timeout på selve pollingen — hænger den i `running` for evigt, poller den for evigt uden at foreslå brugeren at prøve igen.

## `family.js` — Familie-app-grid og bund-navigation

Statisk `FAMILY_APPS`-konfiguration (kids/adults), aktiveres via Indstillinger (`localStorage` `family_kids_apps`/`family_adults_apps`). `shuffle()` her er delt af regnespil og huskespil.
