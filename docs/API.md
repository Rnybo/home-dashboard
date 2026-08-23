# API Reference — Familieoverblik

Base URL: `http://familiekalender.local:8000` (or whichever host/port the server runs on).

## Authentication

Most endpoints require an `x-api-key` header matching `API_KEY` (see `.env`/Settings). Exceptions:
- `GET /api/config` — public, but validated against `Referer`/`Origin` header instead
- `GET /api/first-run`, `GET /api/settings`, `POST /api/settings`, `GET /api/google-oauth/calendars` — used by `settings.html`, no key required
- OAuth callback endpoints (`/auth/google/callback`, `/auth/spotify/callback`) — validated via OAuth `code`, not the API key
- Spotify endpoints and the unauthenticated Cast router (`GET /api/cast/state`, `GET /api/cast/devices`, `/ws/cast`) — no key required; only Cast *control* endpoints (play/pause/etc.) require it

Errors follow FastAPI conventions: `401` for an expired/invalid Aula session, `403` for a missing/wrong API key, `500`/`502` for upstream failures.

## Config & status

| Endpoint | Description |
|---|---|
| `GET /api/config` | API key + dashboard title (public, referer-checked) |
| `GET /api/status` | `{session_valid}` — Aula session check |
| `GET /api/first-run` | `{first_run}` — true if no Aula account configured yet |

## Aula — login & account

| Endpoint | Description |
|---|---|
| `GET /api/login/accounts` | List configured MitID accounts + whether each has a saved token |
| `POST /api/switch-account?account_index=` | Switch active session to another configured account |
| `POST /api/login/start?account_index=` | Start MitID QR login flow for an account |
| `GET /api/login/status` | Poll login progress; returns QR code image when ready |
| `POST /api/login/cancel` | Cancel an in-progress login |
| `POST /api/logout` | Clear session |

## Aula — profile & data

| Endpoint | Description |
|---|---|
| `GET /api/profile-config` | Children list + institution profile IDs |
| `GET /api/profile` | Raw Aula profile data |
| `GET /api/messages?page=` | Message thread list |
| `GET /api/messages/{thread_id}` | Thread content |
| `GET /api/presence?inst_profile_ids=&from_date=&to_date=` | Drop-off/pick-up times |
| `GET /api/presence/pickup-responsibles?child_ids=` | Who's allowed to pick up which child |
| `POST /api/presence/update` | Update presence template(s) — `{updates: [{childId, date, entryTime, exitTime, ...}]}` |
| `GET /api/calendar?inst_profile_ids=&from_date=&to_date=` | Aula calendar events |
| `GET /api/posts?inst_profile_ids=&index=` | Post feed (news/announcements) |
| `GET /api/important-dates?inst_profile_ids=` | Upcoming school dates |
| `GET /api/birthdays?inst_profile_ids=` | Upcoming birthdays |

## Gallery

| Endpoint | Description |
|---|---|
| `GET /api/gallery/albums?inst_profile_ids=` | Album list |
| `GET /api/gallery/albums/{album_id}/media?inst_profile_ids=&index=` | Media in one album |
| `GET /api/gallery/user-media?inst_profile_ids=&index=&limit=` | "Media of you and your children" (all albums) |

## Groups / klasser

| Endpoint | Description |
|---|---|
| `GET /api/groups` | Cached class/group list with member children (see `AulaClient.get_groups_cached()`) |
| `GET /api/groups/{group_id}/contacts` | Contact info for a group's children (only where consent given) |

## Ugebrev / skolekalender

See `backend/CLAUDE.md`'s `ugebrev.py` section for the full architecture (title-based week detection, group-based child resolution, OCR for image-based weekly plans, sync throttling).

| Endpoint | Description |
|---|---|
| `POST /api/ugebrev/sync` | Scan the shared post feed and sync any weekly letters/plans found (background loop every 6h + throttled trigger from Overblik use this) |
| `POST /api/ugebrev/sync-url` | Manual "🎒 Tilføj til skolekalender" — body `{doc_url, anchor_date}`, syncs one specific Google Docs schedule link |
| `GET /api/ugebrev/info?calendar=&week=&year=` | Written note text for one child+week+year (ℹ️ icon in "🎒 Skoledag") |

## Custom events (local calendar)

| Endpoint | Description |
|---|---|
| `GET /api/custom-events` | All locally-stored calendar events (manual + ugebrev-generated) |
| `POST /api/custom-events` | Create an event; syncs to Google Calendar in the background if connected |
| `DELETE /api/custom-events/{event_id}?calendar=` | Remove an event (or just one calendar tag from a shared event) |
| `POST /api/parse-event` | Extract date/time/title from free text — `{text}` in, uses `ANTHROPIC_API_KEY` if set, else a Danish regex fallback |
| `GET /api/custom-events.ics` | ICS feed of all custom events, for external calendar apps |

## Google Calendar

| Endpoint | Description |
|---|---|
| `GET /api/google-calendar?from_date=&to_date=` | Combined ICS feed (all configured calendars + Danish holidays), normalized to one event shape |
| `GET /api/google-oauth/connect` | Get the OAuth consent URL (used to enable writing events to Google) |
| `GET /auth/google/callback` | OAuth redirect target — exchanges code for tokens, saves to `.env` |
| `GET /api/google-oauth/calendars` | List the connected Google account's calendars (public, used by settings.html) |

## Weather & routes

| Endpoint | Description |
|---|---|
| `GET /api/weather` | Hourly forecast from met.no (no API key needed), up to 168h |
| `GET /api/routes` | Commute durations (cycling/walking/driving) from OpenRouteService for each configured destination |

## Spotify

| Endpoint | Description |
|---|---|
| `GET /api/spotify-oauth/connect` | Get the OAuth consent URL |
| `GET /auth/spotify/callback` | OAuth redirect target |
| `GET /api/spotify-oauth/status` | `{connected}` |
| `GET /api/spotify/devices` | Spotify Connect devices (used to match against Cast device names) |
| `GET /api/spotify/search?q=&type=` | Search tracks/albums/playlists/podcasts (`type` comma-separated) |
| `POST /api/spotify/play` | Play a URI on a device — `{uri, device_id}` |

## Cast (Chromecast/Nest)

| Endpoint | Description |
|---|---|
| `GET /api/cast/state` | Current state of all discovered cast devices (no API key) |
| `GET /api/cast/devices` | Device name list (no API key) |
| `WS /ws/cast` | Live state-change stream (no API key) |
| `POST /api/cast/{device}/play` \| `pause` \| `stop` \| `next` \| `previous` | Playback control (requires API key) |
| `POST /api/cast/{device}/seek` \| `seek_abs` \| `mute` \| `volume` | Fine playback control (requires API key) |
| `POST /api/cast/{device}/transfer` | Move playback to another device — `{target, spotify_device_id?}` |

Set `CAST_MOCK=1` in `.env` to use a simulated device set for UI development without real Cast hardware.

## News

| Endpoint | Description |
|---|---|
| `GET /api/news/{feed}?limit=` | DR RSS feed (`feed`: `dr` or `sport`) |
| `GET /api/article-extract?url=` | Server-side readable-text extraction of a `dr.dk` article (avoids iframe/X-Frame-Options issues) |

## Settings

| Endpoint | Description |
|---|---|
| `GET /api/settings` | Current configuration (secrets masked as `"***"`) |
| `POST /api/settings` | Save configuration — masked secret fields (`"***"`) are left untouched, not overwritten |

## File proxies

| Endpoint | Description |
|---|---|
| `GET /api/file-proxy?url=` | Streams an Aula file through the authenticated session (aula.dk/aula-prod.aula.dk only) |
| `GET /api/profile-picture?url=` | Fetches a profile picture, requesting a signed URL if needed (aula.dk/media-prod.aula.dk only) |
