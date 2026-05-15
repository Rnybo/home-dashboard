import requests
import os
import logging
import json

logger = logging.getLogger(__name__)

API_BASE = "https://www.aula.dk/api/v"
API_VERSION = "23"


class AulaClient:
    def __init__(self):
        self.session = requests.Session()
        self.session_valid = False
        self._load_credentials()

    def _load_credentials(self):
        phpsessid = os.getenv("AULA_PHPSESSID", "")
        csrf_token = os.getenv("AULA_CSRF_TOKEN", "")
        self._apply_credentials(phpsessid, csrf_token)

    def _apply_credentials(self, phpsessid: str, csrf_token: str):
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "csrfp-token": csrf_token,
        })
        self.session.cookies.update({
            "PHPSESSID": phpsessid,
            "Csrfp-Token": csrf_token,
        })

    def update_credentials(self, phpsessid: str, csrf_token: str):
        self._apply_credentials(phpsessid, csrf_token)
        self.session_valid = True
        logger.info("Credentials updated in memory")

    def check_session(self) -> bool:
        try:
            resp = self.session.get(
                f"{API_BASE}{API_VERSION}/?method=profiles.getProfileContext&portalrole=guardian",
                verify=True,
                allow_redirects=False
            )
            self.session_valid = resp.status_code == 200 and "data" in resp.json()
        except Exception:
            self.session_valid = False
        return self.session_valid

    def _get(self, method: str, extra_params: str = "") -> dict:
        url = f"{API_BASE}{API_VERSION}/?method={method}{extra_params}"
        resp = self.session.get(url, verify=True)
        if resp.status_code in (401, 403) or resp.url != url:
            self.session_valid = False
            raise PermissionError("Session expired")
        resp.raise_for_status()
        return resp.json()

    def _post(self, method: str, body: dict) -> dict:
        url = f"{API_BASE}{API_VERSION}/?method={method}"
        headers = {
            "content-type": "application/json",
            "csrfp-token": self.session.headers.get("csrfp-token", ""),
        }
        resp = self.session.post(url, data=json.dumps(body), headers=headers, verify=True)
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

    def get_calendar_events(self, inst_profile_ids: list, days_ahead: int = 14) -> list:
        import datetime
        start = datetime.datetime.utcnow().strftime("%Y-%m-%d 00:00:00.0000+0000")
        end = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d 00:00:00.0000+0000")
        data = self._post("calendar.getEventsByProfileIdsAndResourceIds", {
            "instProfileIds": inst_profile_ids,
            "resourceIds": [],
            "start": start,
            "end": end
        })
        return data.get("data") or []
