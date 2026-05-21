# C.F. Aagaards Vej 4 — Family Dashboard

A family dashboard for the Danish school platform Aula, designed for a tablet. Shows weekly schedule, presence times, Google Calendar, weather, commute times, messages, gallery and posts. Features automatic MitID login via Playwright and full offline support via localStorage cache.

## Features

- **Kalender** — Weekly timetable per child with drop-off/pick-up, Aula events, Google Calendar (Fælles), and hour-by-hour weather
- **Today widget** — Daily summary: drop-off/pick-up times, commute times per destination, family Google Calendar events
- **Overblik** — Latest posts, upcoming dates, birthdays
- **Galleri** — Photo albums and media from Aula
- **Beskeder** — Message threads from Aula
- **Weather** — Met.no (no API key): temperature, wind, precipitation per hour in timetable; daily max/min/wind in date headers
- **Commute** — OpenRouteService (free API key): cycling, walking, driving times in Today widget on weekdays
- **Google Calendar** — ICS-based, no OAuth: Rasmus + Maja + Danish public holidays, recurring events supported
- **Notifications** — Badge indicators for unread messages, new posts, new albums; per-view dot indicators in Aula dropdown
- **Offline support** — When Aula session expires, all data (calendar, posts, messages, gallery, dates, birthdays) is served from localStorage cache. Non-Aula sources (Google Calendar, weather, commute) continue updating normally. Small inline banner replaces the old full-screen error.

## Prerequisites

- Python 3.12
- Git

## Local Development

### 1. Clone
```bash
git clone https://github.com/Rnybo/aula-dashboard.git
cd aula-dashboard
```

### 2. Virtual environment
```bash
py -3.12 -m venv venv312
```

### 3. Install dependencies
```bash
.\venv312\Scripts\pip install -r requirements.txt
.\venv312\Scripts\playwright install chromium
```

### 4. Configure `.env`
```bash
copy .env.example .env
```

| Variable | Description |
|---|---|
| `API_KEY` | Random secret key |
| `MITID_USERNAME` | MitID username |
| `MITID_IDENTITY` | Full name as shown in MitID |
| `MITID_USERNAME_2` / `MITID_IDENTITY_2` | Optional second account |
| `AULA_PHPSESSID` / `AULA_CSRF_TOKEN` | Optional existing session cookies |
| `GOOGLE_CALENDAR_ICS_RASMUS` / `_MAJA` | Public ICS links from Google Calendar |
| `WEATHER_LAT` / `WEATHER_LON` | Home coordinates for weather |
| `ORS_API_KEY` | OpenRouteService API key |
| `ORS_ORIGIN_LAT` / `ORS_ORIGIN_LON` | Home coordinates for routing |
| `ORS_DEST_N_NAME/LAT/LON/DEFAULT` | Destination N (N=1,2,3...) |

Generate API key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Start server
```bash
.\venv312\Scripts\uvicorn main:app --host 127.0.0.1 --port 8080
```

Open **http://localhost:8080**

## Google Calendar Setup

1. [calendar.google.com](https://calendar.google.com) → three dots → **Settings and sharing**
2. **Access permissions** → enable **"Make available to public"**
3. **Integrate calendar** → copy **"Public address in iCal format"**

Danish public holidays are included automatically.

## Weather Setup

Fetched from [met.no](https://api.met.no) — no API key. Set `WEATHER_LAT`/`WEATHER_LON` to your home address (right-click in Google Maps → "What's here?").

## Commute Setup

1. Sign up at [openrouteservice.org](https://openrouteservice.org/dev/#/login) → get free API key
2. Find coordinates for each destination via Google Maps
3. Add `ORS_DEST_N_*` for each destination (N = 1, 2, 3...)
4. Set `ORS_DEST_N_DEFAULT`: `cycling-regular`, `foot-walking`, or `driving-car`

Commute cards appear in the Today widget on weekdays only.

## Offline / Session Behaviour

When the Aula session expires a small `⚠️ Aula offline` indicator appears in the header with Login buttons. The dashboard continues to show all previously loaded data from localStorage:

- Calendar events and presence times
- Posts, important dates, birthdays
- Message thread list (last 5) and individual threads (previously opened)
- Child tabs and profile info

Google Calendar, weather and commute continue updating normally. On successful login the page reloads automatically.

## Project Structure

```
aula-dashboard/
├── main.py              # FastAPI — all API endpoints
├── aula_client.py       # Aula API client
├── aula_playwright.py   # MitID login via Playwright
├── requirements.txt
├── .env.example
└── static/
    └── index.html       # Single-page dashboard UI
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/config` | API key (same-origin) |
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
| `POST /api/login/start` | Start MitID login |
| `GET /api/login/status` | Login status + QR |

## Debug Mode

Set `PLAYWRIGHT_DEBUG=true` in `.env` to save screenshots to `debug_screenshots/`.
