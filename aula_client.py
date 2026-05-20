import requests
import os
import logging
import json
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

API_BASE = "https://www.aula.dk/api/v"
API_VERSION = "23"
SESSION_FILE = Path("session.json")


class AulaClient:
    def __init__(self):
        self.session = requests.Session()
        self.session_valid = False
        self._load_credentials()

    def _load_credentials(self):
        phpsessid = None
        csrf_token = None
        if SESSION_FILE.exists():
            try:
                data = json.loads(SESSION_FILE.read_text())
                phpsessid = data.get("PHPSESSID")
                csrf_token = data.get("CSRF_TOKEN")
                logger.info("Loaded credentials from session.json")
            except Exception as e:
                logger.warning(f"Could not read session.json: {e}")
        if not phpsessid:
            phpsessid = os.getenv("AULA_PHPSESSID", "")
        if not csrf_token:
            csrf_token = os.getenv("AULA_CSRF_TOKEN", "")
        self._apply_credentials(phpsessid, csrf_token)

    def _apply_credentials(self, phpsessid: str, csrf_token: str):
        self._csrf_token = csrf_token
        self.session.headers.update({
            "accept": "application/json, text/plain, */*",
            "referer": "https://www.aula.dk/portal/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        })
        self.session.cookies.update({
            "PHPSESSID": phpsessid,
            "Csrfp-Token": csrf_token,
            "initialLogin": "true",
            "profile_change": "16",
        })

    def _post(self, method: str, body: dict) -> dict:
        url = f"{API_BASE}{API_VERSION}/?method={method}"
        resp = self.session.post(url, json=body, verify=True,
            headers={"csrfp-token": self._csrf_token})
        resp.raise_for_status()
        return resp.json()

    def update_credentials(self, phpsessid: str, csrf_token: str):
        self._apply_credentials(phpsessid, csrf_token)
        SESSION_FILE.write_text(json.dumps({
            "PHPSESSID": phpsessid,
            "CSRF_TOKEN": csrf_token
        }))
        self.session_valid = True
        logger.info("Credentials updated and saved to session.json")

    def check_session(self) -> bool:
        try:
            resp = self.session.get(
                f"{API_BASE}{API_VERSION}/?method=profiles.getProfilesByLogin",
                verify=True,
                allow_redirects=False
            )
            data = resp.json()
            self.session_valid = resp.status_code == 200 and data.get("status", {}).get("code") == 0
        except Exception:
            self.session_valid = False
        return self.session_valid

    def _get(self, method: str, extra_params: str = "") -> dict:
        url = f"{API_BASE}{API_VERSION}/?method={method}{extra_params}"
        resp = self.session.get(url, verify=True)
        if resp.status_code == 401:
            self.session_valid = False
            raise PermissionError("Session expired")
        resp.raise_for_status()
        return resp.json()

    def get_profile(self) -> dict:
        return self._get("profiles.getProfileContext", "&portalrole=guardian")

    def get_threads(self, page: int = 0) -> list:
        data = self._get("messaging.getThreads", f"&sortOn=date&orderDirection=desc&page={page}")
        return data.get("data", {}).get("threads", [])

    def get_messages_for_thread(self, thread_id: int, page: int = 0) -> dict:
        data = self._get("messaging.getMessagesForThread", f"&threadId={thread_id}&page={page}")
        return data.get("data", {})

    def get_calendar_events(self, inst_profile_ids: list, from_date: str = None, to_date: str = None) -> list:
        today = datetime.date.today()
        if not from_date:
            from_date = today.strftime("%Y-%m-%d")
        if not to_date:
            to_date = (today + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        tz_offset = datetime.datetime.now().astimezone().strftime("%z")
        tz_str = f"{tz_offset[:3]}:{tz_offset[3:]}"
        start = f"{from_date} 00:00:00.0000{tz_str}"
        end = f"{to_date} 23:59:59.9990{tz_str}"
        data = self._post("calendar.getEventsByProfileIdsAndResourceIds", {
            "instProfileIds": inst_profile_ids,
            "resourceIds": [],
            "start": start,
            "end": end
        })
        return data.get("data") or []

    def get_albums(self, inst_profile_ids: list, index: int = 0, limit: int = 24) -> list:
        ids_param = "".join(f"&filterInstProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("gallery.getAlbums", f"&index={index}&limit={limit}&sortOn=mediaCreatedAt&orderDirection=desc&filterBy=all{ids_param}")
        return data.get("data", []) or []

    def get_album_media(self, album_id: int, inst_profile_ids: list = None, index: int = 0, limit: int = 40) -> dict:
        ids_param = "".join(f"&filterInstProfileIds[]={i}" for i in (inst_profile_ids or []))
        data = self._get("gallery.getMedia", f"&albumId={album_id}&index={index}&limit={limit}&sortOn=uploadedAt&orderDirection=desc&filterBy=all{ids_param}")
        return data.get("data", {})

    def get_user_media(self, inst_profile_ids: list, index: int = 0, limit: int = 12) -> dict:
        ids_param = "".join(f"&filterInstProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("gallery.getMedia", f"&userSpecificAlbum=true&index={index}&limit={limit}&sortOn=uploadedAt&orderDirection=desc&filterBy=all{ids_param}")
        return data.get("data", {})

    def get_posts(self, inst_profile_ids: list, index: int = 0, limit: int = 10) -> dict:
        ids_param = "".join(f"&institutionProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("posts.getAllPosts", f"&parent=profile&index={index}{ids_param}")
        return data.get("data", {})

    def get_important_dates(self, inst_profile_ids: list, limit: int = 20) -> list:
        data = self._get("calendar.getImportantDates", f"&limit={limit}&include_today=false")
        items = data.get("data", []) or []
        # Deduplicate — same event appears once per child, key on title+start
        seen, result = set(), []
        for item in items:
            key = item.get("title","") + "|" + item.get("startDateTime","")[:10]
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def get_birthdays(self, inst_profile_ids: list) -> list:
        # Get institution codes from profile first
        try:
            profile = self.get_profile()
            inst_codes = list({
                r.get("institutionCode")
                for r in (profile.get("data", {}).get("institutionProfile", {}).get("relations") or [])
                if r.get("institutionCode")
            })
        except Exception:
            inst_codes = []
        if not inst_codes:
            return []
        today = datetime.date.today()
        end = today + datetime.timedelta(days=30)
        tz_offset = datetime.datetime.now().astimezone().strftime("%z")
        tz_str = f"{tz_offset[:3]}:{tz_offset[3:]}"
        codes_param = "".join(f"&instCodes[]={c}" for c in inst_codes)
        data = self._get("calendar.getBirthdayEventsForInstitutions",
            f"&start={today}T00:00:00.000{tz_str}&end={end}T23:59:59.000{tz_str}{codes_param}")
        return data.get("data", []) or []

    def get_presence(self, inst_profile_ids: list, from_date: str = None, to_date: str = None) -> list:
        today = datetime.date.today()
        if not from_date:
            from_date = today.strftime("%Y-%m-%d")
        if not to_date:
            to_date = (today + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        ids_param = "".join(f"&filterInstitutionProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("presence.getPresenceTemplates", f"{ids_param}&fromDate={from_date}&toDate={to_date}")
        return data.get("data", {}).get("presenceWeekTemplates", []) or []
