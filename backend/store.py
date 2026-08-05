"""
backend/store.py — delte hjælpefunktioner til custom events storage
Adskilt fra main.py for at undgå circular imports med routers
"""
import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger("store")

ROOT = Path(__file__).parent.parent
CUSTOM_EVENTS_FILE = ROOT / "custom_events.json"
_custom_events_lock = threading.Lock()


def load_custom_events() -> list:
    with _custom_events_lock:
        try:
            return json.loads(CUSTOM_EVENTS_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.warning(f"Kunne ikke læse custom_events.json ({e}) — returnerer tom liste. "
                            f"Filen er IKKE overskrevet, så data er ikke tabt.")
            return []


def save_custom_events(events: list):
    with _custom_events_lock:
        CUSTOM_EVENTS_FILE.write_text(
            json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
        )
