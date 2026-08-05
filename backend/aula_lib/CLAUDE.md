# backend/aula_lib/ — vendored `nickknissen/aula` bibliotek

**Dette er tredjeparts-kode** (vendored fra github.com/nickknissen/aula), ikke skrevet i samme stil/konventioner som resten af projektet. Behandl ændringer her med ekstra forsigtighed — det er lettere at bryde noget subtilt i MitID/SAML-flowet end i projektets eget kode.

## To bevidste patches — rør ikke uden at forstå dem

Begge sidder i `auth/mitid_client.py`:

1. **POST 302-redirect håndtering (~linje 411-419):** httpx følger ikke automatisk redirects på POST-requests. Efter MitID-completion-steppet tjekkes eksplicit for `301/302/303` med en `location`-header, samt for tekst-baseret "Object moved to /loginoption" (nogle gange kommer redirect'et ikke som en rigtig HTTP-redirect, men som HTML-indhold der beskriver det).
2. **Foretræk privat identitet ved flere MitID-identiteter (~linje 469-478):** Hvis en bruger har flere identiteter tilknyttet MitID (fx både en privat og en professionel), vælges automatisk den der matcher `["privat", "private", "person", "borger"]` i navnet — ellers ville login vælge den første i listen uden garanti for at det er den rigtige.

## Hvad bruges rent faktisk

`aula_auth.py` (i `backend/`) bruger **kun** `create_client()` og `_refresh_token_via_oidc()` fra `auth_flow.py`, samt `MitIDAuthClient` direkte fra `auth/mitid_client.py` for selve login-flowet. De højere-niveau bekvemmeligheds-funktioner i `auth_flow.py` (`authenticate()`, `authenticate_and_create_client()`) er **ubrugte** i dette projekt — de er beregnet til CLI-brug/Home Assistant-integrationer og har deres egen token-storage-antagelse. Bliv ikke forvirret over at de findes; de kører ikke i praksis her.

## To uafhængige API-version-tracking-mekanismer — ikke en fejl, men letter at forveksle

`api_client.py`'s `_request_with_version_retry()` har **sin egen** auto-bump-på-410-logik (starter fra `const.py`'s hardcodede `API_VERSION`, øger +1 ved 410, op til 5 forsøg) — helt uafhængig af `backend/aula_version.py`. Denne bruges kun under selve login/`init()`-flowet og **persisterer ikke** på tværs af genstarter (nulstilles til `const.py`'s hardcodede værdi hver gang). Det er `backend/aula_version.py` (se `backend/CLAUDE.md`) der håndterer den vedvarende version til den løbende data-hentning i `aula_client.py`. To forskellige mekanismer til to forskellige livscyklusser — bevidst, ikke duplikeret ved en fejl.
