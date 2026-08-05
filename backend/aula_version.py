"""Tracks the current Aula API version and self-heals when Aula retires it.

Aula periodically bumps their API version and returns HTTP 410 Gone on the
old one for every method. This module persists the last known-good version
(api_version.json, project root) and automatically bumps + retries once when
a 410 is seen, so the dashboard recovers on its own instead of needing a
manual code fix each time.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("aula_version")

_FILE = Path(__file__).parent.parent / "api_version.json"
_FALLBACK = 24  # last known-good version as of this code being written


def get_version() -> int:
    try:
        return int(json.loads(_FILE.read_text())["version"])
    except Exception:
        return _FALLBACK


def _bump(current: int) -> int:
    new_version = current + 1
    try:
        _FILE.write_text(json.dumps({"version": new_version}))
    except Exception as e:
        logger.warning(f"Kunne ikke gemme ny API-version: {e}")
    logger.warning(f"Aula API v{current} er lukket (410 Gone) — skifter automatisk til v{new_version}")
    return new_version


def _url(version: int, query: str) -> str:
    base = f"https://www.aula.dk/api/v{version}/"
    return f"{base}?{query}" if query else base


_MAX_RETRIES = 5  # matches aula_lib's own version-retry budget


def get(session, query: str = "", **kwargs):
    """requests-based GET with automatic version bump+retry on 410 Gone."""
    version = get_version()
    for _ in range(_MAX_RETRIES):
        resp = session.get(_url(version, query), **kwargs)
        if resp.status_code != 410:
            return resp
        version = _bump(version)
    return resp


def post(session, query: str = "", **kwargs):
    """requests-based POST with automatic version bump+retry on 410 Gone."""
    version = get_version()
    for _ in range(_MAX_RETRIES):
        resp = session.post(_url(version, query), **kwargs)
        if resp.status_code != 410:
            return resp
        version = _bump(version)
    return resp


async def async_get(client, query: str = "", **kwargs):
    """httpx-based GET with automatic version bump+retry on 410 Gone."""
    version = get_version()
    for _ in range(_MAX_RETRIES):
        resp = await client.get(_url(version, query), **kwargs)
        if resp.status_code != 410:
            return resp
        version = _bump(version)
    return resp
