# frontend/ — index.html, settings.html

> **Status:** Fuldt gennemgået. Se `js/CLAUDE.md`, `js/apps/CLAUDE.md`, `css/CLAUDE.md` for resten af frontend.

## `index.html`

Ren markup + inline styles for modaler/overlays — al reel logik ligger i `js/`-filerne (se load-rækkefølgen dokumenteret i `js/CLAUDE.md`). Alle `.aula-dd-item`-elementer har `data-view="..."`-attributter som JS bruger til aktiv-tilstand og badge-visning — **behold disse attributter synkroniseret** hvis du tilføjer et nyt dropdown-punkt (både her og i `js/globals.js`/`js/aula.js`).

`<h1>🏠 Familieoverblik</h1>` er en hardcoded placeholder — `initConfig()` (i `globals.js`) overskriver den med den konfigurerede `dashboard_title` ved boot. Kort "flash" af forkert titel før JS kører er forventet, ikke en fejl.

## `vendor/pdfjs/`

Bundlet offline pdf.js (v3.11.174, UMD-build — **ikke** npm-pakkens ESM-build, som pdf.js v4+ kun leverer). Bruges af `calendar.js`'s `openFileModal()` til at rendere PDF-vedhæftninger på canvas, fordi Android WebView (Fully Kiosk) ikke har en indbygget PDF-viewer. Ingen internetafhængighed efter installation — filerne er statiske og hentes via `git pull` som alt andet i `frontend/`. Opgradér ikke til pdf.js v4+ uden at bytte til ESM-imports i `viewer.html`/`viewer.js`.

## `vendor/docx-preview/`

Bundlet offline `docx-preview.js` (v0.3.5) + `jszip.min.js` (ekstern afhængighed — **skal loades før** `docx-preview.js` i `viewer.html`, UMD-builden bundler den ikke selv). Renderer kun `.docx` (OOXML) til HTML/CSS — **ikke** det gamle binære `.doc`-format, som stadig ender i den generiske download-fallback i `calendar.js`. Samme offline-princip som `vendor/pdfjs/`.

## `manifest.json` + `sw.js` — PWA

`sw.js` cacher **kun statiske app-shell-filer** (html/css/js/vendor/ikoner) — rører aldrig `/api/*`, det er `cache.js`'s domæne (localStorage, egen TTL-logik). To cache-lag der konkurrerer om samme data var en reel fejlkilde tidligere; hold dem strikt adskilt.

**Network-first, ikke cache-first** — bevidst valg efter Fully Kiosk-cache-sagaen (ændringer der ikke slog igennem efter deploy, se `js/CLAUDE.md`/git-historik). `sw.js` forsøger altid netværket først og falder kun tilbage til cache hvis fetch fejler (reel offline). Skift ikke til cache-first uden at forstå hvorfor det blev undgået her.

**Kræver HTTPS (eller `localhost`) for at virke overhovedet** — service workers registrerer ikke i en "insecure context". Over almindeligt `http://familiekalender.local` (nuværende tablet-opsætning) vil `navigator.serviceWorker.register()` simpelthen fejle stille (fanget i en `.catch(() => {})` i `index.html` — ingen synlig fejl, bare ingen offline-cache/rigtig install-prompt). iPhones "Tilføj til hjemmeskærm" virker uafhængigt af dette (bruger `apple-mobile-web-app-*`-meta-tags, ikke manifestet). Virker fuldt ud den dag der lægges HTTPS på (fx via Tailscale) — ingen kodeændring nødvendig da.

`CACHE_NAME` i `sw.js` er versioneret (`familieoverblik-shell-v1`) — **bump versionsnummeret ved strukturelle ændringer** i `SHELL_FILES`-listen (nye/omdøbte js-filer), `activate`-handleren rydder automatisk gamle cache-versioner op.

## `settings.html`

Selvstændig side, egen inline `<style>` og `<script>` — deler ingen kode med `index.html`/`js/`. Tre uafhængige `<script>`-blokke: hovedindstillinger, Familie Apps (gemmes i `localStorage`, ikke server-side!), og børnelås (samme `localStorage`-nøgle og hash-funktion som `calendar.js`'s `clHash()` — **hold disse to implementationer identiske** hvis du ændrer PIN-logikken, ellers kan en PIN sat på én side ikke låses op fra den anden).

**Google/Spotify OAuth-tilslutning virker kun fra samme enhed som serveren kører på** — begge udbyderes redirect-URI er hardcoded til `localhost`/`127.0.0.1` (kan ikke være dynamisk, skal matche det der er registreret hos Google/Spotify præcist). Prøver man at tilslutte fra en telefon mens dashboardet kører på tabletten, fejler det stille. Der er nu en synlig advarsel i UI'et om dette — fjern den ikke uden at løse det underliggende problem (ville kræve en anden OAuth-flow-type, ikke en simpel kodeændring).

`/api/settings`'s GET-endpoint returnerer hemmeligheder (Google/Spotify client secret, Anthropic-nøgle) som `"***"` hvis de allerede er sat — `saveSettings()` sender denne maskerede værdi tilbage uændret, og backend'en genkender `"***"` som "rør ikke ved denne" i stedet for at overskrive den rigtige hemmelighed. Fungerer korrekt allerede, men vær opmærksom på mønsteret hvis du tilføjer et nyt hemmeligt felt — husk maskering begge veje.
