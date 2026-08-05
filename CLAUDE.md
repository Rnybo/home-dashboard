# CLAUDE.md — Familieoverblik (aula-dashboard)

Vægmonteret family-dashboard til en Samsung-tablet (Fully Kiosk Browser via Termux). Backend: FastAPI/Python. Frontend: rå HTML/CSS/JS, ingen build-step. Integrerer Aula (skole), Google Calendar, Spotify, Chromecast/Nest, vejr (met.no), pendlerruter (OpenRouteService), og børnespil.

**Ejer/udvikler:** Rasmus, arbejder alene på projektet. Deployment til tabletten sker altid manuelt af Rasmus (`git pull && bash install.sh`) — deployer aldrig derop uopfordret.

## Struktur — læs det relevante undermappe-CLAUDE.md

| Sti | Indhold |
|---|---|
| `backend/CLAUDE.md` | Kørselsmodel (sync/async, threadpool-regler), session/Aula-data (`aula_client.py`, `aula_auth.py`), API-version-selvheling, MQTT, cast, Google/Spotify token-refresh |
| `backend/routers/CLAUDE.md` | Alle API-endpoints, gruppéret efter feature |
| `backend/aula_lib/CLAUDE.md` | Vendored MitID/OAuth-bibliotek — hvilke patches der er bevidste, rør ikke uden at forstå dem |
| `frontend/CLAUDE.md` | `index.html`/`settings.html` — markup, OAuth-gotchas |
| `frontend/js/CLAUDE.md` | App-skal + feature-moduler — **script-load-rækkefølgen er kritisk**, læs dette før du tilføjer en ny fil |
| `frontend/js/apps/CLAUDE.md` | Børnenes spil — drag-and-drop-guard-mønster |
| `frontend/css/CLAUDE.md` | Styling, responsive breakpoints, kendt (udokumenteret) kontrast-mønster |

## Gennemgående principper fundet/etableret under den systematiske code review (august 2026)

Disse mønstre gik igen på tværs af hele kodebasen og er værd at kende, uanset hvilken fil du arbejder i:

1. **Aula-siden ændrer sig uden varsel** — API-version-lukninger (`410 Gone`) og nye rollenavne (`"early-student"`) har begge brudt dashboardet uden forudgående varsel fra Aula. Kode der taler med Aula bør være defensiv over for dette (blocklists frem for whitelists, auto-retry på versionsfejl) — se `backend/aula_client.py` og `backend/aula_version.py`.
2. **Vis aldrig succes du ikke har bekræftet.** Flere steder viste UI'et en grøn "gemt/virkede"-besked uanset om det underliggende API-kald rent faktisk lykkedes (fanget stille i en tom `catch`). Ret det til at faktisk tjekke svaret, hver gang du støder på mønsteret.
3. **Brug `data-*`-attributter, aldrig regex på `onclick`-strengen**, til at finde data fra et DOM-element. Det gamle mønster brød stille flere steder (bindestreg i view-navne, forkert antal på hinanden følgende tal i en streng).
4. **Script-navnekollisioner er stille i `frontend/js/`** — to filer der definerer samme funktionsnavn giver ingen fejl, den sidst indlæste fil vinder. Ramte cache-laget for vejr/Google-kalender tidligere.
5. **Test altid live mod den rigtige Aula-session efter en session/auth-ændring** — sessionsopførsel (cookie-rotation, token-refresh-races) viser sig ofte kun i praksis, ikke i kode-læsning alene.

## Arbejdsflow

Rasmus beskriver problemet → Claude diagnosticerer og retter → Rasmus tester lokalt → Rasmus siger "Push" for commit+push. Rettelser skal være kirurgiske og kun omfatte det rapporterede problem, medmindre andet er eksplicit aftalt (som under denne systematiske review). Syntax-valider altid før push (`ast.parse` for Python, `node --check` for JS, brace-balance for CSS), og kør et live smoke-test af den lokale server hvor det er muligt.
