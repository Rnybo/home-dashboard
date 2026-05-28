import requests
import os
import logging
import json
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

API_BASE = "https://www.aula.dk/api/v"
API_VERSION = "23"
SESSION_FILE = Path(__file__).parent.parent / "session.json"
GROUPS_CACHE_FILE = Path(__file__).parent.parent / "groups_cache.json"


class AulaClient:
    def __init__(self):
        self.session = requests.Session()
        self.session_valid = False
        self._profile_cache = None  # cached profile data, invalidated on new credentials
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
        })

    def _post(self, method: str, body: dict) -> dict:
        url = f"{API_BASE}{API_VERSION}/?method={method}"
        resp = self.session.post(url, json=body, verify=True,
            headers={"csrfp-token": self._csrf_token})
        resp.raise_for_status()
        return resp.json()

    def update_credentials(self, phpsessid: str, csrf_token: str):
        self._apply_credentials(phpsessid, csrf_token)
        self._profile_cache = None  # invalidate cache on new session
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
        if not self.session_valid:
            self._profile_cache = None
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
        if self._profile_cache is None:
            self._profile_cache = self._get("profiles.getProfileContext", "&portalrole=guardian")
        return self._profile_cache

    def _get_institutions(self) -> list:
        """Return institutions list from cached profile."""
        return self.get_profile().get("data", {}).get("institutions") or []

    def _get_guardian_profile_ids(self) -> list:
        """Guardian institutionProfileId per institution."""
        return [i.get("institutionProfileId") for i in self._get_institutions() if i.get("institutionProfileId")]

    def _get_inst_codes(self) -> list:
        """Institution codes (e.g. G20341) for all institutions."""
        return list({i.get("institutionCode") for i in self._get_institutions() if i.get("institutionCode")})

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
        all_ids = list(dict.fromkeys(self._get_guardian_profile_ids() + inst_profile_ids))
        ids_param = "".join(f"&institutionProfileIds[]={i}" for i in all_ids)
        data = self._get("posts.getAllPosts", f"&parent=profile&index={index}&limit={limit}{ids_param}")
        return data.get("data", {})

    def get_important_dates(self, inst_profile_ids: list, limit: int = 20) -> list:
        data = self._get("calendar.getImportantDates", f"&limit={limit}&include_today=false")
        items = data.get("data", []) or []
        # Deduplicate — merge belongsToProfiles from duplicates
        seen, result = {}, []
        for item in items:
            key = item.get("title","") + "|" + item.get("startDateTime","")[:10]
            if key not in seen:
                seen[key] = item
                result.append(item)
            else:
                # Merge child IDs from duplicate entry
                existing = seen[key]
                merged = list(set((existing.get("belongsToProfiles") or []) + (item.get("belongsToProfiles") or [])))
                existing["belongsToProfiles"] = merged
        return result

    def get_birthdays(self, inst_profile_ids: list) -> list:
        inst_codes = self._get_inst_codes()
        if not inst_codes:
            return []
        today = datetime.date.today()
        end = today + datetime.timedelta(days=30)
        tz_offset = datetime.datetime.now().astimezone().strftime("%z")
        codes_param = "".join(f"&instCodes[]={c}" for c in inst_codes)
        url = f"https://www.aula.dk/api/v23/?method=calendar.getBirthdayEventsForInstitutions&start={today}T00:00:00.000%2B{tz_offset[1:3]}%3A{tz_offset[3:]}&end={end}T23:59:59.000%2B{tz_offset[1:3]}%3A{tz_offset[3:]}{codes_param}"
        resp = self.session.get(url, verify=True)
        if resp.status_code == 401:
            raise PermissionError("Session expired")
        resp.raise_for_status()
        return resp.json().get("data", []) or []

    def _pic_url(self, pic: dict, size: str = "200x200") -> str:
        """Build a stable media URL from a profilePicture object."""
        if not pic:
            return ""
        key = pic.get("key", "")
        if not key:
            return ""
        # key may already include extension e.g. "path/abc123.jpg"
        # strip extension before appending size suffix
        base = key.rsplit(".", 1)[0] if "." in key.split("/")[-1] else key
        return f"https://media-prod.aula.dk/{base}_{size}.jpg"

    def get_profile_picture_url(self, signed_url: str) -> tuple:
        """Fetch a signed profile picture URL and return (content_type, bytes)."""
        r = self.session.get(signed_url, timeout=10)
        r.raise_for_status()
        return r.headers.get("Content-Type", "image/jpeg"), r.content

    def get_groups(self) -> list:
        """Return children's primary groups with all children and their parents."""
        profile_data = self.get_profile().get("data", {})
        institutions = profile_data.get("institutions") or []

        # Build lookup of own children: institutionProfileId -> {name, photoUrl}
        own_children = {}
        for inst in institutions:
            for child in (inst.get("children") or []):
                pic = child.get("profilePicture") or {}
                own_children[child.get("id")] = {
                    "name": child.get("name", ""),
                    "photoUrl": self._pic_url(pic),
                }

        # Collect direct group IDs from each institution
        seen_group_ids = {}
        for inst in institutions:
            for group in (inst.get("groups") or []):
                if group.get("membershipType") == "direct":
                    seen_group_ids[group["id"]] = group.get("name", f"Gruppe {group['id']}")

        if not seen_group_ids:
            return []

        result = []
        for group_id, group_name in seen_group_ids.items():
            try:
                memberships_data = self._get("groups.getMemberships", f"&groupId={group_id}")
                memberships = memberships_data.get("data", {}).get("memberships", []) or []

                # Find which of our own children are in this group
                my_kids_in_group = [
                    info for cid, info in own_children.items()
                    if any(
                        m.get("institutionProfile", {}).get("id") == cid
                        for m in memberships
                    )
                ]

                children = []
                CHILD_ROLES = {"daycare", "student", "child", "pupil", "schoolchild"}
                for m in memberships:
                    if m.get("institutionRole") not in CHILD_ROLES:
                        continue
                    ip = m.get("institutionProfile", {})
                    photo_url = self._pic_url(ip.get("profilePicture") or {})

                    parents = []
                    for rel in (ip.get("relations") or []):
                        if rel.get("role") == "guardian":
                            parents.append({
                                "name": rel.get("fullName", ""),
                                "gender": rel.get("gender", ""),
                                "photoUrl": self._pic_url(rel.get("profilePicture") or {}),
                            })

                    children.append({
                        "id": ip.get("id"),
                        "name": ip.get("fullName", ""),
                        "gender": ip.get("gender", ""),
                        "photoUrl": photo_url,
                        "isOwnChild": ip.get("id") in own_children,
                        "parents": parents,
                    })

                children.sort(key=lambda c: c["name"])
                result.append({
                    "id": group_id,
                    "name": group_name,
                    "myChildren": my_kids_in_group,
                    "children": children,
                })
            except Exception as e:
                logger.warning(f"Could not get group {group_id}: {e}")

        # Write cache
        try:
            GROUPS_CACHE_FILE.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not write groups cache: {e}")

        return result

    def get_groups_cached(self) -> list:
        """Return cached groups if available, otherwise fetch live."""
        try:
            return self.get_groups()
        except Exception:
            if GROUPS_CACHE_FILE.exists():
                try:
                    return json.loads(GROUPS_CACHE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return []

    def get_contact_list(self, group_id: int) -> list:
        """Fetch all children with contact info for a group (paginated)."""
        results = []
        page = 1
        while True:
            data = self._get(
                "profiles.getContactlist",
                f"&groupId={group_id}&filter=child&field=name&page={page}&order=asc"
            )
            contacts = data.get("data", []) or []
            if not contacts:
                break
            for c in contacts:
                pic = c.get("profilePicture") or {}
                pic_key = pic.get("key", "")
                birthday = None
                if c.get("birthday"):
                    try:
                        birthday = c["birthday"][:10]  # YYYY-MM-DD
                    except Exception:
                        pass

                parents = []
                for r in (c.get("relations") or []):
                    if r.get("institutionRole") not in ("guardian", "parent"):
                        continue
                    if not r.get("userHasGivenConsentToShowContactInformation", True):
                        continue
                    r_pic = r.get("profilePicture") or {}
                    addr = r.get("address") or {}
                    parents.append({
                        "name": r.get("fullName", ""),
                        "relation": r.get("relation", ""),
                        "gender": r.get("gender", ""),
                        "mobile": r.get("mobilePhoneNumber", ""),
                        "email": r.get("email", ""),
                        "address": f"{addr.get('street', '')} {addr.get('postalCode', '')} {addr.get('postalDistrict', '')}".strip(),
                        "photoUrl": self._pic_url(r.get("profilePicture") or {}),
                        "photoSignedUrl": (r.get("profilePicture") or {}).get("url", ""),
                        "consent": r.get("userHasGivenConsentToShowContactInformation", False),
                    })

                results.append({
                    "id": c.get("id"),
                    "name": c.get("fullName", ""),
                    "birthday": birthday,
                    "photoUrl": self._pic_url(c.get("profilePicture") or {}),
                    "photoSignedUrl": (c.get("profilePicture") or {}).get("url", ""),
                    "parents": parents,
                })
            if len(contacts) < 20:
                break
            page += 1
        return results

    def get_child_name(self, inst_profile_id: str) -> str:
        """Return first name of a child by institutionProfileId, using cached profile."""
        try:
            for inst in self._get_institutions():
                for child in (inst.get("children") or []):
                    if str(child.get("id")) == str(inst_profile_id):
                        return child.get("name", "").split()[0]
        except Exception:
            pass
        return ""

    def get_presence(self, inst_profile_ids: list, from_date: str = None, to_date: str = None) -> list:
        today = datetime.date.today()
        if not from_date:
            from_date = today.strftime("%Y-%m-%d")
        if not to_date:
            to_date = (today + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        ids_param = "".join(f"&filterInstitutionProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("presence.getPresenceTemplates", f"{ids_param}&fromDate={from_date}&toDate={to_date}")
        return data.get("data", {}).get("presenceWeekTemplates", []) or []
