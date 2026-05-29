"""
backend/cast_service.py — Google Cast / Nest device monitoring
Opdager Cast-enheder via mDNS og abonnerer på media status events.
Publicerer til MQTT: familieoverblik/cast/{device}/state
Kør standalone: python -m backend.cast_service
"""
import json
import logging
import threading
import time
from typing import Callable

log = logging.getLogger("cast_service")

# Normaliseret state per enhed
_state: dict[str, dict] = {}
_listeners: list[Callable] = []
_lock = threading.Lock()

try:
    import pychromecast
    _CAST_AVAILABLE = True
except ImportError:
    _CAST_AVAILABLE = False
    log.warning("pychromecast ikke installeret — Cast deaktiveret")


def _empty_state(name: str) -> dict:
    return {
        "device":  name,
        "app":     None,
        "state":   "IDLE",
        "title":   None,
        "artist":  None,
        "album":   None,
        "image":   None,
        "volume":  None,
    }


def _notify(device: str, state: dict):
    with _lock:
        _state[device] = state
        cbs = list(_listeners)
    for cb in cbs:
        try:
            cb(device, state)
        except Exception as e:
            log.warning("Cast listener fejl: %s", e)


class _MediaListener:
    def __init__(self, name: str):
        self.name = name

    def new_media_status(self, status):
        if not status:
            return
        state = {
            "device":  self.name,
            "app":     status.media_metadata.get("metadataType", None),
            "state":   status.player_state,  # PLAYING, PAUSED, IDLE, BUFFERING
            "title":   status.media_metadata.get("title"),
            "artist":  status.media_metadata.get("artist") or status.media_metadata.get("subtitle"),
            "album":   status.media_metadata.get("albumName"),
            "image":   next((i["url"] for i in status.media_metadata.get("images", []) if i.get("url")), None),
            "volume":  None,
        }
        log.info("Cast %s: %s — %s", self.name, state["state"], state["title"])
        _notify(self.name, state)


class _StatusListener:
    def __init__(self, name: str):
        self.name = name

    def new_cast_status(self, status):
        if not status:
            return
        with _lock:
            current = dict(_state.get(self.name, _empty_state(self.name)))
        current["volume"] = round(status.volume_level, 2) if status.volume_level is not None else None
        current["app"]    = status.display_name or current.get("app")
        if status.status_text:
            current["title"] = status.status_text
        _notify(self.name, current)


class _ConnectionListener:
    def __init__(self, name: str, cc):
        self.name = name
        self.cc = cc

    def new_connection_status(self, status):
        log.info("Cast %s forbindelsesstatus: %s", self.name, status.status)
        if status.status == "CONNECTED":
            pass
        elif status.status in ("DISCONNECTED", "LOST"):
            _notify(self.name, _empty_state(self.name))


# ── Offentlig API ──────────────────────────────────────────────────────────────

_chromecasts: dict[str, object] = {}  # name → pychromecast instance


def get_state() -> dict:
    """Returnerer seneste state for alle opdagede enheder."""
    with _lock:
        return dict(_state)


def add_listener(cb: Callable):
    """Tilføj callback der kaldes ved state-ændring: cb(device, state)."""
    with _lock:
        _listeners.append(cb)


def control_device(device: str, action: str, **kwargs) -> bool:
    """Styr en Cast-enhed: play, pause, stop, volume."""
    cc = _chromecasts.get(device)
    if not cc:
        log.warning("control_device: enhed '%s' ikke fundet", device)
        return False
    try:
        mc = cc.media_controller
        if action == "play":    mc.play()
        elif action == "pause": mc.pause()
        elif action == "stop":  mc.stop()
        elif action == "volume":
            cc.set_volume(float(kwargs.get("level", 0.5)))
        return True
    except Exception as e:
        log.warning("control_device fejl: %s", e)
        return False


def start(known_hosts: list[str] | None = None):
    """
    Start Cast discovery og monitoring i baggrundstråd.
    known_hosts: liste af IP-adresser til direkte forbindelse (omgår mDNS).
    """
    if not _CAST_AVAILABLE:
        log.warning("pychromecast ikke tilgængeligt — Cast service starter ikke")
        return
    t = threading.Thread(target=_run, args=(known_hosts,), daemon=True, name="cast-service")
    t.start()
    log.info("Cast service startet")


def _run(known_hosts: list[str] | None):
    chromecasts = []
    browser = None

    try:
        import zeroconf as zc_module

        def _on_cast(chromecast):
            name = chromecast.name
            log.info("Cast: fandt %s (%s)", name, chromecast.host)
            _chromecasts[name] = chromecast
            chromecast.register_status_listener(_StatusListener(name))
            chromecast.media_controller.register_status_listener(_MediaListener(name))
            chromecast.register_connection_listener(_ConnectionListener(name, chromecast))
            chromecast.wait()
            _notify(name, _empty_state(name))

        zeroconf_instance = zc_module.Zeroconf()

        if known_hosts:
            log.info("Cast: forbinder direkte til %s", known_hosts)
            chromecasts, browser = pychromecast.get_chromecasts(
                known_hosts=known_hosts,
                zeroconf_instance=zeroconf_instance,
            )
            for cc in chromecasts:
                _on_cast(cc)
        else:
            log.info("Cast: starter mDNS discovery med callback...")
            browser = pychromecast.get_chromecasts(
                blocking=False,
                callback=_on_cast,
                zeroconf_instance=zeroconf_instance,
            )

        # Hold tråden i live — browser holder mDNS subscription aktiv
        while True:
            time.sleep(30)

    except Exception as e:
        log.error("Cast service fejl: %s", e, exc_info=True)
    finally:
        if browser:
            try:
                browser.stop_discovery()
            except Exception:
                pass


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def on_state(device, state):
        print(f"\n[{device}] {state['state']} — {state['title']} af {state['artist']}")
        print(f"  App: {state['app']}, Volumen: {state['volume']}")

    add_listener(on_state)
    start()

    print("Lytter efter Cast-enheder — tryk Ctrl+C for at stoppe")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStoppes")
