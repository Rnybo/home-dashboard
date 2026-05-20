# Aula Dashboard

A family dashboard for the Danish school platform Aula, designed for a tablet (e.g. Android tablet or Google Nest Hub 1024×600). Shows weekly schedule, presence times, calendar events, messages, gallery and Google Calendar for the whole family. Features automatic MitID login via Playwright.

## Features

- 📅 **Kalender** — Weekly timetable per child with drop-off/pick-up times, Aula events and Google Calendar (Fælles)
- 🏠 **Overblik** — Latest posts, upcoming dates, birthdays
- 🖼️ **Galleri** — Photo albums and media from Aula
- 📬 **Beskeder** — Message threads from Aula
- 📅 **Google Calendar** — Combined family calendar (Rasmus + Maja + Danish holidays)
- 🔔 **Notifications** — Badge indicators for unread messages and new posts/albums
- 🔐 **Auto-login** — Automatic MitID login via Playwright when session expires

## Prerequisites

- Python 3.12
- Git

## Local Development

### 1. Clone the repo
```bash
git clone https://github.com/Rnybo/aula-dashboard.git
cd aula-dashboard
```

### 2. Create virtual environment with Python 3.12
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
| `MITID_IDENTITY` | Your full name as shown in MitID (e.g. `Rasmus Fogh Nybo`) |
| `MITID_USERNAME_2` | Optional: second MitID account username |
| `MITID_IDENTITY_2` | Optional: second MitID account full name |
| `AULA_PHPSESSID` | Optional: existing Aula session cookie (skips login on first start) |
| `AULA_CSRF_TOKEN` | Optional: existing Aula CSRF token |
| `GOOGLE_CALENDAR_ICS_RASMUS` | Public ICS link for first person's Google Calendar |
| `GOOGLE_CALENDAR_ICS_MAJA` | Public ICS link for second person's Google Calendar |

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

To get the ICS link for a Google Calendar:

1. Go to [calendar.google.com](https://calendar.google.com)
2. Click the three dots next to your calendar → **Settings and sharing**
3. Under **"Access permissions"** → enable **"Make available to public"**
4. Scroll down to **"Integrate calendar"** → copy the **"Public address in iCal format"**

Danish public holidays are automatically included from:
```
https://calendar.google.com/calendar/ical/da.danish%23holiday%40group.v.calendar.google.com/public/basic.ics
```

## Session Login Flow

When the session expires, the dashboard shows a red banner. Click it (or select an account) to start automatic MitID login:

1. Playwright opens a headless browser and navigates to aula.dk
2. Enters your MitID username automatically
3. The dashboard displays the MitID approval screen (push notification or QR code)
4. **Approve in your MitID app** or **scan the QR code** with your phone
5. Playwright selects your private identity automatically
6. Dashboard reloads with a fresh session

Multi-account support: add `MITID_USERNAME_2` / `MITID_IDENTITY_2` (up to `_5`) to enable login buttons for multiple accounts.

## Project Structure

```
aula-dashboard/
├── main.py              # FastAPI app — all API endpoints
├── aula_client.py       # Aula API client (sessions, profile, calendar, gallery etc.)
├── aula_playwright.py   # Automated MitID login via Playwright
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── static/
    └── index.html       # Dashboard UI (single-page app, no framework)
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/config` | Returns API key (same-origin only) |
| `GET /api/status` | Session validity check |
| `GET /api/profile-config` | Children and institution IDs (dynamic) |
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
| `POST /api/login/start` | Start MitID login flow |
| `GET /api/login/status` | Login flow status + QR code |

## Debug Mode

Set `PLAYWRIGHT_DEBUG=true` in `.env` to save screenshots at each login step to the `debug_screenshots/` folder.
