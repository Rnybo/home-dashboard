# Familieoverblik — Family Dashboard

A family dashboard for the Danish school platform Aula, designed for a wall-mounted tablet. Shows weekly schedule, presence times, Google Calendar, weather, commute times, messages, gallery and posts. Features automatic MitID login with refresh token (no Playwright) and full offline support via localStorage cache.

## Features

- **Kalender** — Weekly timetable per child with drop-off/pick-up, Aula events, Google Calendar (Fælles), and hour-by-hour weather
- **Today widget** — Daily summary: drop-off/pick-up times, commute times per destination, family Google Calendar events
- **Overblik** — Latest posts, upcoming dates, birthdays
- **Galleri** — Photo albums and media from Aula
- **Beskeder** — Message threads from Aula, with attachment preview (PDF via bundled offline pdf.js, .docx via bundled offline docx-preview — Android WebView has no native viewer for either; other file types get a download fallback)
- **Weather** — Met.no (no API key): temperature, wind, precipitation per hour in timetable; daily max/min/wind in date headers
- **Commute** — OpenRouteService (free API key): cycling, walking, driving times in Today widget on weekdays
- **Google/Apple Calendar** — ICS-based, no OAuth: supports multiple calendars, recurring events
- **Notifications** — Badge indicators for unread messages, new posts, new albums; per-view dot indicators in Aula dropdown
- **Offline support** — When Aula session expires, all data is served from localStorage cache
- **Settings page** — Configure everything via browser at `/settings.html` — no terminal needed
- **Spotify search** — Search songs, albums, playlists and podcasts directly from the cast widget (requires active Spotify playback)
- **Familie** — Optional dropdown with Børn and Voksne pages; configured via Settings → Familie Apps (shown only when at least one app is enabled)

## Quick Install (Android/Termux)

```bash
curl -sSL https://raw.githubusercontent.com/Rnybo/home-dashboard/main/scripts/install.sh | sh
```

Then open: **http://familiekalender.local:8000/settings.html**

## Local Development (PC/Mac)

### 1. Clone
```bash
git clone https://github.com/Rnybo/home-dashboard.git
cd home-dashboard
```

### 2. Virtual environment
```bash
py -3.12 -m venv venv
```

### 3. Install dependencies
```bash
venv\Scripts\pip install -r requirements.txt
```

### 4. Configure
```bash
copy .env.example .env
```
Edit `.env` or use the settings page after starting the server.

| Variable | Description |
|---|---|
| `API_KEY` | Random secret key (auto-generated if empty) |
| `DASHBOARD_TITLE` | Header title shown on dashboard (default: Hjem) |
| `MITID_USERNAME` | MitID username (phone/CPR) |
| `MITID_IDENTITY` | Full name as shown in MitID |
| `MITID_USERNAME_2` / `MITID_IDENTITY_2` | Optional second account |
| `GOOGLE_CALENDAR_ICS` | Public ICS link from Google/Apple Calendar |
| `GOOGLE_CALENDAR_NAME` | Display name for calendar |
| `WEATHER_LAT` / `WEATHER_LON` | Home coordinates for weather |
| `ORS_API_KEY` | OpenRouteService API key (optional) |
| `ORS_ORIGIN_LAT` / `ORS_ORIGIN_LON` | Home coordinates for routing |
| `ORS_DEST_N_NAME/LAT/LON/DEFAULT` | Destination N (N=1,2,3...) |
| `ANTHROPIC_API_KEY` | Optional — improves date parsing from messages |

### 5. Installer Mosquitto MQTT broker (anbefalet)
```
winget install mosquitto
```
`start.bat` starter Mosquitto automatisk — hvis ikke installeret, kører dashboardet stadig men uden MQTT.

### 6. Start server
```bash
start.bat
```
Or manually:
```bash
venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000
```

Open **http://familiekalender.local:8000**

## Calendar Setup

**Google Calendar:**
1. [calendar.google.com](https://calendar.google.com) → three dots → **Settings and sharing**
2. **Integrate calendar** → copy **"Public address in iCal format"**

**Apple Calendar:**
1. Calendar app → Edit → Share Calendar → enable Public → copy URL
2. Replace `webcal://` with `https://`

Danish public holidays are included automatically.

## Weather Setup

Fetched from [met.no](https://api.met.no) — no API key needed. Set `WEATHER_LAT`/`WEATHER_LON` (right-click in Google Maps → "What's here?").

## Commute Setup

1. Sign up at [openrouteservice.org](https://openrouteservice.org/dev/#/login) → free API key
2. Add `ORS_DEST_N_*` for each destination (N = 1, 2, 3...)
3. `ORS_DEST_N_DEFAULT`: `cycling-regular`, `foot-walking`, or `driving-car`

## Project Structure

```
home-dashboard/
├── backend/
│   ├── main.py                     # FastAPI app setup, middleware, startup tasks
│   ├── store.py                    # Thread-safe custom_events.json r/w
│   ├── google_utils.py             # Google Calendar OAuth helpers
│   ├── aula_client.py              # Aula API client
│   ├── aula_auth.py               # MitID login via OAuth2 + refresh token (no Playwright)
│   └── routers/
│       ├── aula.py                 # Aula endpoints (login, profile, posts, gallery...)
│       ├── custom.py               # Custom events CRUD + parse + ICS feed
│       ├── google.py               # Google Calendar + OAuth endpoints
│       ├── settings.py             # Settings GET/POST
│       └── weather.py              # Weather (Met.no)
├── frontend/
│   ├── index.html                  # Single-page dashboard UI
│   └── settings.html               # Browser-based configuration
├── scripts/
│   ├── install.sh                  # One-click Android/Termux installer
│   ├── start.bat                   # Windows start script
│   ├── full_sync.py                # Deploy to tablet via SSH
│   └── login_node.js               # Node.js MitID login for Android
├── tests/
│   └── test_api.py                 # API test suite (run: python tests/test_api.py)
├── docs/
│   └── API.md                      # Full API reference
├── requirements.txt
└── .env.example
```

## Kendte begrænsninger

### iCloud-brugere — lokal synkronisering

Events oprettet direkte i dashboardet ("Gem til Familieoverblik") synkroniseres automatisk til Google Calendar via OAuth. iCloud understøttes **ikke** som synkroniseringsmål — CalDAV-skrivning kræver en separat integration der endnu ikke er implementeret.

**Anbefalet workaround for iCloud-brugere:**

Brug Google Calendar som mellemled ("hub"). Google Calendar kan vises direkte i iOS Kalender og iCloud-appen, og events oprettet i dashboardet synkroniseres til Google og vises der automatisk.

1. Opret en Google-konto (eller brug eksisterende)
2. Tilføj Google Calendar til iOS: **Indstillinger → Kalender → Konti → Tilføj konto → Google**
3. Sæt Google Calendar op i dashboardet (se Google Calendar Setup herunder)
4. Events oprettet i dashboardet synkroniseres til Google og vises automatisk i iOS Kalender

**Alternativt** — hvis du kun vil *læse* en iCloud-kalender i dashboardet (uden at skrive tilbage):
1. Åbn Kalender på Mac eller iOS
2. Vælg kalender → Del → aktivér **Offentlig kalender** → kopiér URL
3. Erstat `webcal://` med `https://`
4. Tilføj URL som `GOOGLE_CALENDAR_ICS` i `.env`

ICS-læsning virker fuldt ud for alle kilder (Google, iCloud, Outlook, Rejseplanen m.fl.).

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/config` | API key + dashboard config |
| `GET /api/status` | Session check |
| `GET /api/profile-config` | Children + institution IDs |
| `GET /api/calendar` | Aula events |
| `GET /api/presence` | Drop-off/pick-up |
| `GET /api/posts` | Posts/announcements |
| `GET /api/important-dates` | Upcoming school dates |
| `GET /api/birthdays` | Upcoming birthdays |
| `GET /api/messages` | Thread list |
| `GET /api/messages/{id}` | Thread content |
| `GET /api/gallery/albums` | Albums |
| `GET /api/gallery/albums/{id}/media` | Album media |
| `GET /api/gallery/user-media` | Media with your children |
| `GET /api/google-calendar` | Combined Google Calendar (ICS) |
| `GET /api/weather` | Hourly weather from met.no |
| `GET /api/routes` | Commute times from OpenRouteService |
| `GET /api/custom-events` | Local calendar events |
| `GET /api/custom-events.ics` | ICS feed for calendar apps |
| `POST /api/login/start` | Start MitID login |
| `GET /api/login/status` | Login status + QR |
| `GET /api/settings` | Get configuration |
| `POST /api/settings` | Save configuration |
