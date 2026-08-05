# frontend/css/ — Styling

> **Status:** Fuldt gennemgået: `main.css` (app-skal, kalender, modaler, klasse, cast), `family.css` (familie-apps, regnespil, huskespil, stavespil). `css/apps/`-mappen findes men er tom.

Ingen preprocessor, ingen build-step — rå CSS, custom properties (`:root { --blue, --border, --bg, --radius, --hour-h, --time-col }`) i `main.css`. Mange grundige media queries til forskellige tablet/telefon-orienteringer og -størrelser (landscape ≤860px/≤620px højde, portrait, portrait-tablet, telefon-portrait) — **test altid ændringer i flere af disse**, ikke kun standard-visningen, hvis du rører ved layout eller skriftstørrelser.

## Rettet i dette review

- **Dødt CSS fjernet:** `#cast-home-widget`-blokken (matcher `castRenderHomeWidget()`-fjernelsen i `cast.js`).
- **Udefineret variabel:** `.cast-transfer-btn` brugte `var(--text)` uden fallback og uden at `--text` nogensinde var defineret i `:root` — tilføjet `, #333`-fallback.
- **ID-typo:** `#view-app-stavespil` (family.css) matchede intet — det rigtige DOM-id er `view-app-spell`. Flyttet ind i den delte selector-liste for familie-app-views.
- **Lav kontrast, forkert tema-farve:** `.rs-setup-hint` brugte `#94a3b8` (den mørke temas lyse tekstfarve — kopieret fra `huskespillets` mørke skærme) på regnespillets/stavespillets **lyse** baggrund, hvilket gav en kontrastration på ~2:1. Rettet til `#64748b`, som allerede bruges konsekvent til lignende sekundær-tekst i samme lyse tema (`.rs-level-desc`, `.mem-grid-desc`).
- **Skriftstørrelse for aflæsning på afstand:** Dashboardet er vægmonteret og læses ofte fra et par meters afstand — dag-headers, dato-tal, "i dag"-widgettens indhold og uret i toppen er blevet gjort en anelse større (`.day-header` 0.78→0.85rem, `.date-num` 1.1→1.25rem, today-widget-rækker 0.78→0.85rem, `header #clock` 0.95→1.05rem). Bevidst **konservative** stigninger — testet kun for balancerede CSS-blokke, ikke visuelt i en rigtig browser. **Tjek på tabletten at intet nu skærer af eller overlapper.**

## Ikke rettet — bevidst overladt til dig

**Gennemgående lav-kontrast mønster:** Sekundær-tekst i hele `main.css` bruger konsekvent lyse grå (`#888`, `#999`, `#aaa`, `#bbb`) på hvid/lys baggrund — det giver kontrastrationer på typisk 2.3–3.5:1, under WCAG AA's 4.5:1-minimum for normal tekst. Det er brugt i dusinvis af steder (tidsstempler, meta-info, hints) og er klart en **bevidst, konsekvent designbeslutning** (ikke en fejl som `.rs-setup-hint` var) — at ændre det er derfor en visuel identitets-beslutning, ikke en bugfix, og jeg har ikke ændret det uden at du kan se resultatet. Hvis du vil forbedre det: overvej at mørkne skalaen et hak (`#999→#767676`, `#aaa→#888`, `#bbb→#999`) — bevarer det visuelle hierarki, forbedrer læsbarheden. Sig til hvis du vil have mig til at gennemføre det.

## Touch-mål

Allerede godt tilgodeset — spil-knapper (`.tal-btn` 72×72px), niveau/kategori-knapper i regnespil/huskespil/stavespil, og PIN-tastaturet er alle rummelige nok til børnefingre på en tablet. Ingen ændringer nødvendige.
