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

**`openNyhed()` viser artikler i `post-modal`** (samme modal som Aula-opslag bruger) med indhold fra `/api/article-extract` (se `backend/routers/CLAUDE.md`). To andre tilgange blev prøvet og bekræftet **ikke virker** på den faktiske tablet: iframe blokeres af DR's `X-Frame-Options`, og `window.open()`/ny fane understøttes ikke af Fully Kiosk Browser. Server-side udtræk af artiklens brødtekst er den løsning der reelt virker i denne opsætning — hold fast i den, prøv ikke iframe eller window.open igen for eksternt indhold på dette projekt.

## `tal.js` — Simpel tæller

Ingen fund.
