# frontend/js/ — Client-side app

> **Status:** `frontend/js/` er nu fuldt gennemgået: `globals.js`, `app.js`, `auth.js`, `utils.js`, `cache.js`, `family.js`, `calendar.js`, `klasse.js`, `gallery.js`, `aula.js`, `presence_edit.js`, `cast.js`. Se `js/apps/CLAUDE.md` for børnenes spil, `js/CLAUDE.md`-nabofiler i `css/` og roden for resten af frontend.

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
- **`openFileModal()` router efter filendelse** — PDF renderes via en bundlet offline pdf.js-viewer (`frontend/vendor/pdfjs/viewer.html`), `.docx` via en bundlet offline docx-preview.js-viewer (`frontend/vendor/docx-preview/viewer.html`) — begge fordi Android WebView (Fully Kiosk) ikke har indbygget PDF/Office-rendering som desktop Chrome. Gammelt binært `.doc` kan **ikke** parses af docx-preview og ender derfor i den generiske fallback. Billeder går uden om modalen helt (lightbox). Alt WebView ikke kan vise (xlsx/pptx/zip/ukendt/`.doc`) viser et fallback-skærmbillede (`#file-modal-fallback`) med download-knap i stedet for at forsøge en iframe der ville fejle stille. Tilføj nye filtyper til `INLINE_TEXT_EXT`/`IMAGE_EXT` eller en ny `else if`-gren i stedet for at ændre selve routing-logikken.
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

## `gallery.js` — Aula-galleri + lightbox

Ren, ingen fund. Bruger allerede `data-idx`-attributter korrekt (ikke onclick-streng-parsing). Tastatur-navigation i lightbox (pil venstre/højre, Escape).

## `aula.js` — badges, beskeder, "kommende events"-sidebar

- **`setBadge()`'s dropdown-prik-indikator bruger `data-view`** (samme fix som `switchView()` i `globals.js`) — brugte tidligere regex på `onclick`.
- **`openMsg()`'s "Tilføj til kalender"-knapper bruger nu et deterministisk id** (`m.id ?? array-index`) i både render- og listener-tilknytningstrinnet. De brugte tidligere *forskellige* fallback-værdier ved manglende `m.id` (tilfældigt tal ved render, tom streng ved lytter-tilknytning) — en besked uden `id`-felt ville derfor få en knap der så klikbar ud, men ikke gjorde noget.

## `presence_edit.js` — rediger hente/bringe-tider

Solidt eksempel på korrekt fejlhåndtering — tjekker faktisk `ok`-status per barn i svaret og viser præcise fejl/succes-beskeder. Sammenlign med den tidligere bug i `saveEventLocal()` (nu rettet) for at se forskellen mellem god og dårlig håndtering af samme mønster.

## `cast.js` — Chromecast/Spotify-afspiller-widget

Solidt modul — progress-bars med live-interpolation, in-place DOM-opdatering under afspilning (undgår fuld re-render der ville afbryde en bruger midt i en interaktion), WebSocket + polling-fallback, korrekt fejlvisning ved Spotify-søgning/afspilning/transfer.

- **`castRenderHomeWidget()` og `_castPanelDirty` er fjernet** — dødt kode. Førstnævnte var en helt færdigbygget, men aldrig-kaldt funktion hvis mål-element (`#cast-home-widget`) ikke engang fandtes i `index.html`. Sidstnævnte var et flag der blev sat men aldrig læst — den faktiske live-opdatering af et åbent panel sker via `castUpdatePanelInPlace()`, uafhængigt af flaget.
- Har et fuldt **mock-mode** til Spotify-søgning (`window._spotifyMockEnabled`, monkey-patcher `apiFetch` midlertidigt) — praktisk til UI-udvikling uden en rigtig Spotify-forbindelse.
