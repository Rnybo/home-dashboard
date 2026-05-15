# Aula Dashboard

A dashboard for Danish school platform Aula, designed for Google Nest Hub (1024×600). Shows weekly schedule, calendar events and messages for your children. Features automatic MitID login via Playwright.

## Prerequisites

- Python 3.12
- Git
- A Railway account (railway.app)

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
| `MITID_USERNAME` | Your MitID username (phone number or CPR) |
| `MITID_IDENTITY` | Your full name as shown in MitID (e.g. `Rasmus Fogh Nybo`) |
| `AULA_PHPSESSID` | Optional: existing Aula session cookie (avoids login on first start) |
| `AULA_CSRF_TOKEN` | Optional: existing Aula CSRF token |

Generate a random API key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Start the server
```bash
.\venv312\Scripts\uvicorn main:app --reload
```

Open **http://localhost:8000**

## Session Login Flow

When the session expires, the dashboard shows a red banner. Click it to start automatic MitID login:

1. Playwright opens a headless browser and navigates to aula.dk
2. Enters your MitID username automatically
3. The dashboard displays the MitID approval screen (push notification or QR code)
4. **Approve in your MitID app** or **scan the QR code** with your phone
5. Playwright selects your private identity automatically
6. Dashboard reloads with a fresh session

## Deployment (Railway)

### 1. Push to GitHub
```bash
git add .
git commit -m "your message"
git push origin main
```

### 2. Railway setup
- Connect your GitHub repo in Railway
- Add environment variables under **Variables**:
  - `API_KEY`
  - `MITID_USERNAME`
  - `MITID_IDENTITY`
- Railway uses the `Dockerfile` and `railway.json` automatically

### 3. Access
Your app will be available at your Railway domain (e.g. `https://aulanybo.up.railway.app`)

## Project Structure

```
aula-dashboard/
├── main.py              # FastAPI app - API endpoints
├── aula_client.py       # Aula API wrapper
├── aula_playwright.py   # Automated MitID login
├── requirements.txt
├── Dockerfile
├── railway.json         # Railway deployment config
└── static/
    └── index.html       # Dashboard UI (optimized for Nest Hub 1024x600)
```

## Kids Configuration

The dashboard is currently configured for two children. To change names or profile IDs, edit `static/index.html`:

```javascript
const CHILDREN = [
  { name: 'Aksel', id: 5620584 },
  { name: 'Max',   id: 5620590 }
];
```

Profile IDs can be found by calling `/api/profile` while logged in and looking at `data.institutionProfile.relations[].id`.

## Debug Mode

Set `PLAYWRIGHT_DEBUG=true` in your `.env` to save screenshots at each login step:
```
debug_01_login_page.png
debug_02_unilogin_page.png
...
```
