# Familieoverblik — Family Dashboard

A family dashboard for the Danish school platform Aula, designed for a wall-mounted tablet. Shows weekly schedule, presence times, Google Calendar, weather, commute times, messages, gallery and posts. Features automatic MitID login via Playwright and full offline support via localStorage cache.

## Features

- **Kalender** — Weekly timetable per child with drop-off/pick-up, Aula events, Google Calendar (Fælles), and hour-by-hour weather
- **Today widget** — Daily summary: drop-off/pick-up times, commute times per destination, family Google Calendar events
- **Overblik** — Latest posts, upcoming dates, birthdays
- **Galleri** — Photo albums and media from Aula
- **Beskeder** — Message threads from Aula
- **Weather** — Met.no (no API key): temperature, wind, precipitation per hour in timetable; daily max/min/wind in date headers
- **Commute** — OpenRouteService (free API key): cycling, walking, driving times in Today widget on weekdays
- **Google/Apple Calendar** — ICS-based, no OAuth: supports multiple calendars, recurring events
- **Notifications** — Badge indicators for unread messages, new posts, new albums; per-view dot indicators in Aula dropdown
- **Offline support** — When Aula session expires, all data is served from localStorage cache
- **Settings page** — Configure everything via browser at `/settings.html` — no terminal needed

## Quick Install (Android/Termux)

```bash
curl -sSL https://raw.githubusercontent.com/Rnybo/aula-dashboard/main/install.sh | sh
```

Then open: **http://familiekalender.local:8000/settings.html**

## Local Development (PC/Mac)

### 1. Clone
```bash
git clone https://github.com/Rnybo/aula-dashboard.git
cd aula-dashboard
```

### 2. Virtual environment
```bash
py -3.12 -m venv venv
```

### 3. Install dependencies
```bash
venv\Scripts\pip install -r requirements.txt
venv\Scripts\playwright install chromium
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

### 5. Start server
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
aula-dashboard/
├── main.py                    # FastAPI — all API endpoints
├── aula_client.py             # Aula API client
├── aula_playwright.py         # MitID login via Playwright
├── install.sh                 # One-click Android/Termux installer
├── start.bat                  # Windows start script
├── requirements.txt
├── .env.example
└── static/
    ├── index.html             # Single-page dashboard UI
    └── settings.html          # Browser-based configuration
```

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
