# C.F. Aagaards Vej 4 — Family Dashboard

A family dashboard for the Danish school platform Aula, designed for a tablet. Shows weekly schedule, presence times, calendar events, messages, gallery, Google Calendar, live weather, and commute times. Features automatic MitID login via Playwright.

## Features

- **Kalender** — Weekly timetable per child with drop-off/pick-up, Aula events, Google Calendar, and hour-by-hour weather in the timetable
- **Today widget** — At-a-glance daily summary: drop-off/pick-up, commute times, family Google Calendar events
- **Overblik** — Latest posts, upcoming dates, birthdays
- **Galleri** — Photo albums and media from Aula
- **Beskeder** — Message threads from Aula
- **Weather** — Met.no integration (no API key): temperature, wind, precipitation per hour; daily max/min/wind in date headers
- **Commute** — OpenRouteService routing (free API key): cycling, walking, driving times in Today widget on weekdays
- **Google Calendar** — ICS-based, no OAuth: Rasmus + Maja + Danish public holidays. Recurring events supported.
- **Notifications** — Badge indicators for unread messages, new posts, new albums; per-view dot indicators in Aula dropdown
- **Offline-resilient** — When Aula session expires, dashboard stays functional with cached data; small offline indicator in header replaces the old full-screen banner

## Prerequisites

- Python 3.12
- Git

## Local Development

### 1. Clone the repo
```bash
git clone https://github.com/Rnybo/aula-dashboard.git
cd aula-dashboard
```

### 2. Create virtual environment
```bash
py -3.12 -m venv venv312
```

### 3. Install dependencies
```bash
.\venv312\Scripts\pip install -r requirements.txt
.\venv312\Scripts\playwright install chromium
```

### 4. Configure environment
Copy `.env.example` to `.env` and fill in your values:
```bash
copy .env.example .env
```

| Variable | Description |
|---|---|
| `API_KEY` | Random secret key to protect the API |
| `MITID_USERNAME` | Your MitID username |
| `MITID_IDENTITY` | Your full name as shown in MitID |
| `MITID_USERNAME_2` | Optional: second MitID account username |
| `MITID_IDENTITY_2` | Optional: second MitID account full name |
| `AULA_PHPSESSID` | Optional: existing Aula session cookie |
| `AULA_CSRF_TOKEN` | Optional: existing Aula CSRF token |
| `GOOGLE_CALENDAR_ICS_RASMUS` | Public ICS link for first person's Google Calendar |
| `GOOGLE_CALENDAR_ICS_MAJA` | Public ICS link for second person's Google Calendar |
| `WEATHER_LAT` / `WEATHER_LON` | Home address coordinates for weather |
| `ORS_API_KEY` | OpenRouteService API key (free at openrouteservice.org) |
| `ORS_ORIGIN_LAT` / `ORS_ORIGIN_LON` | Home address coordinates for routing |
| `ORS_DEST_N_NAME` | Destination name (N = 1, 2, 3...) |
| `ORS_DEST_N_LAT` / `ORS_DEST_N_LON` | Destination coordinates |
| `ORS_DEST_N_DEFAULT` | Default mode: `cycling-regular`, `foot-walking`, or `driving-car` |

Generate a random API key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Start the server
```bash
.\venv312\Scripts\uvicorn main:app --host 127.0.0.1 --port 8080
```

Open **http://localhost:8080**

## Google Calendar Setup

1. Go to [calendar.google.com](https://calendar.google.com)
2. Three dots next to your calendar → **Settings and sharing**
3. **"Access permissions"** → enable **"Make available to public"**
4. **"Integrate calendar"** → copy **"Public address in iCal format"**

Danish public holidays are included automatically.

## Weather Setup

Fetched from [met.no](https://api.met.no) — no API key required. Set `WEATHER_LAT`/`WEATHER_LON` to your home address coordinates (right-click in Google Maps → "What's here?").

## Commute Setup

1. Sign up at [openrouteservice.org](https://openrouteservice.org/dev/#/login) → get a free API key
2. Find coordinates for each destination via Google Maps
3. Add `ORS_DEST_N_*` variables for each destination (N = 1, 2, 3...)
4. Set `ORS_DEST_N_DEFAULT` to `cycling-regular`, `foot-walking`, or `driving-car`

Commute cards appear in the Today widget on weekdays only.

## Session Behaviour

When the Aula session expires, a small inline indicator appears in the header. All cached data (calendar, posts, messages, gallery) remains visible. Google Calendar, weather, and commute continue to update normally. Click the indicator to log in again automatically.

## Project Structure

```
aula-dashboard/
├── main.py              # FastAPI app — all API endpoints
├── aula_client.py       # Aula API client
├── aula_playwright.py   # Automated MitID login via Playwright
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── static/
    └── index.html       # Dashboard UI (single-page app)
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/config` | Returns API key (same-origin only) |
| `GET /api/status` | Session validity check |
| `GET /api/profile-config` | Children and institution IDs |
| `GET /api/calendar` | Aula calendar events |
| `GET /api/presence` | Drop-off/pick-up times |
| `GET /api/posts` | Aula posts/announcements |
| `GET /api/important-dates` | Upcoming school dates |
| `GET /api/birthdays` | Upcoming birthdays |
| `GET /api/messages` | Message thread list |
| `GET /api/messages/{id}` | Full message thread |
| `GET /api/gallery/albums` | Photo albums |
| `GET /api/gallery/albums/{id}/media` | Album media |
| `GET /api/gallery/user-media` | Media featuring your children |
| `GET /api/google-calendar` | Combined Google Calendar (ICS-based) |
| `GET /api/weather` | Hourly weather from met.no |
| `GET /api/routes` | Commute times from OpenRouteService |
| `POST /api/login/start` | Start MitID login flow |
| `GET /api/login/status` | Login flow status + QR code |

## Debug Mode

Set `PLAYWRIGHT_DEBUG=true` in `.env` to save screenshots at each login step to `debug_screenshots/`.
