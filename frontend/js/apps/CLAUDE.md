# frontend/js/apps/ — Børnenes apps og spil

> **Status:** Fuldt gennemgået: `tal.js`, `nyheder.js`, `regnespil.js`, `huskespil.js`, `stavespil.js`.

Alle apps deler samme mønster: `render<Navn>App()` bygger hele view'et som en HTML-streng og sætter `innerHTML` — ingen frameworks, ingen build-step. `familyAppBack('family-kids'|'family-adults')` (i `family.js`) navigerer tilbage.

## Drag-and-drop (regnespil.js, stavespil.js)

Begge bruger et identisk pointer-event-baseret drag-mønster (opret et "ghost"-element der følger fingeren, tjek overlap med dropzone ved `pointerup`). **Vigtig regel: `pointerdown`-handleren skal ignorere nye touches mens en drag allerede er i gang** (`if (ss.dragging) return;` / `if (rs.dragging) return;`). Uden dette kan en anden finger/håndflade der rører en anden brik midt i et træk overskrive det aktive drag-state og efterlade det første "ghost"-element hængende på skærmen for evigt — meget plausibelt med børn på en tablet. Hvis du tilføjer et nyt drag-and-drop-spil, kopiér mønsteret **med** dette guard, ikke uden.

`pointercancel` skal altid rydde op i ghost-elementet lige såvel som `pointerup` — ellers overlever spøgelsesbrikker en afbrudt touch (fx opkald, notifikation).

## `huskespil.js` — Memory

Understøtter flere spillere (med tur-dialog), 6 kategorier med rigtige billeder (`/static/memory/<kategori>/<fil>.jpg`, dansk oversættelses-mapping i `MEM_DANISH`), 3 grid-størrelser, og en billedvælger hvor brugeren selv kan vælge hvilke billeder der skal indgå (`memOpenPicker()`). Solidt, ingen aktive bugs.

## `regnespil.js` — Regnestykker med drag-and-drop-svar

4 sværhedsgrader, 4 regnearter (kan kombineres), stjerne-baseret streak, konfetti-eksplosion (`rsBurst()`) ved korrekt svar. `rsGenerateNumbers()`'s division-gren lader bevidst det viste tal (`a`) vokse med tabel-størrelsen — ikke en fejl.

## `stavespil.js` — Stavning med bogstav-brikker

3 sværhedsgrader (skjuler 1/2/3 bogstaver af et ord), genbruger huskespillets billeder hvor muligt. Samme drag-mønster som `regnespil.js` — se guard-reglen ovenfor.

## `nyheder.js` — DR-nyheder

`openNyhed()` åbner artikler med `window.open(url,'_blank')`. **Iframe-indlejring blev prøvet og bekræftet blokeret** af DR's `X-Frame-Options`/CSP-headers (testet direkte på tabletten, august 2026) — `window.open` er den eneste løsning der reelt virker for eksterne sider som ikke er under egen kontrol. Prøv ikke iframe igen for DR-artikler uden en server-side proxy der omskriver hele siden (stor opgave, ikke gjort).

## `tal.js` — Simpel tæller

Ingen fund.
