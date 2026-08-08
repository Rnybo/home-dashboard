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


# ── Ugebrev-brødtekst ────────────────────────────────────────────────────────
# Separat lille JSON-fil (ikke en del af custom_events.json — det er ikke
# kalenderevents, det er den narrative tekst fra selve ugebrevet, hentet af
# skolekalender.js's info-ikon). Nøgle: "cal-child-<id>|<year>|<week>".
UGEBREV_NOTES_FILE = ROOT / "ugebrev_notes.json"
_ugebrev_notes_lock = threading.Lock()


def load_ugebrev_notes() -> dict:
    with _ugebrev_notes_lock:
        try:
            return json.loads(UGEBREV_NOTES_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.warning(f"Kunne ikke læse ugebrev_notes.json ({e}) — returnerer tom dict.")
            return {}


def save_ugebrev_note(key: str, text: str):
    with _ugebrev_notes_lock:
        try:
            notes = json.loads(UGEBREV_NOTES_FILE.read_text(encoding="utf-8"))
        except Exception:
            notes = {}
        notes[key] = text
        UGEBREV_NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
