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


def get_devices() -> list[str]:
    """Returnerer navne på alle kendte Cast-enheder."""
    with _lock:
        return list(_chromecasts.keys())


def transfer_playback(source: str, target: str) -> dict:
    """
    Overfør afspilning fra source til target.
    Returnerer {"ok": bool, "method": "spotify"|"media"|"error", "detail": str}
    """
    src_state = _state.get(source, {})
    app = (src_state.get("app") or "").lower()

    # ── Spotify: brug Transfer Playback API ───────────────────────────────────
    if "spotify" in app:
        try:
            from backend.spotify_utils import get_spotify_access_token
            import requests as req
            token = get_spotify_access_token()
            if not token:
                return {"ok": False, "method": "spotify", "detail": "Spotify ikke forbundet"}

            # Find Spotify device id der matcher target-navn
            r = req.get("https://api.spotify.com/v1/me/player/devices",
                        headers={"Authorization": f"Bearer {token}"}, timeout=8)
            r.raise_for_status()
            devices = r.json().get("devices", [])

            # Fuzzy match på navn
            target_lower = target.lower()
            match = next(
                (d for d in devices if target_lower in d["name"].lower() or d["name"].lower() in target_lower),
                None
            )
            if not match:
                names = [d["name"] for d in devices]
                return {"ok": False, "method": "spotify", "detail": f"Ingen Spotify-enhed matcher '{target}'. Fandt: {names}"}

            r2 = req.put("https://api.spotify.com/v1/me/player",
                         headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                         json={"device_ids": [match["id"]], "play": True}, timeout=8)
            if r2.status_code in (200, 204):
                return {"ok": True, "method": "spotify", "detail": match["name"]}
            return {"ok": False, "method": "spotify", "detail": f"Spotify API fejl {r2.status_code}"}
        except Exception as e:
            return {"ok": False, "method": "spotify", "detail": str(e)}

    # ── Anden media: stop source, start på target ─────────────────────────────
    src_cc = _chromecasts.get(source)
    tgt_cc = _chromecasts.get(target)
    if not src_cc or not tgt_cc:
        return {"ok": False, "method": "media", "detail": "Enhed ikke fundet"}
    try:
        mc = src_cc.media_controller
        status = mc.status
        if not status or not status.content_id:
            return {"ok": False, "method": "media", "detail": "Ingen aktiv media URL på kildeenhed"}
        url          = status.content_id
        content_type = status.content_type or "video/mp4"
        position     = status.current_time or 0

        src_cc.media_controller.stop()

        tgt_cc.wait(timeout=5)
        tgt_cc.media_controller.play_media(url, content_type, current_time=position)
        return {"ok": True, "method": "media", "detail": target}
    except Exception as e:
        return {"ok": False, "method": "media", "detail": str(e)}


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
        if action == "play":      mc.play()
        elif action == "pause":   mc.pause()
        elif action == "stop":    mc.stop()
        elif action == "next":    mc.queue_next()
        elif action == "previous":mc.queue_prev()
        elif action == "seek":
            current = mc.status.current_time if mc.status else 0
            mc.seek(max(0, current + float(kwargs.get("delta", 0))))
        elif action == "volume":
            cc.set_volume(float(kwargs.get("level", 0.5)))
        return True
    except Exception as e:
        log.warning("control_device fejl: %s", e)
        return False


_stop_event = threading.Event()


def stop():
    """Stop Cast service og luk alle forbindelser."""
    _stop_event.set()
    for cc in list(_chromecasts.values()):
        try:
            cc.disconnect()
        except Exception:
            pass
    log.info("Cast service stoppet")


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

        def _connect_cast(chromecast):
            name = chromecast.name
            try:
                chromecast.wait(timeout=10)
                initial = _empty_state(name)
                try:
                    s = chromecast.status
                    if s:
                        initial["volume"] = round(s.volume_level, 2) if s.volume_level is not None else None
                        initial["app"] = s.display_name or None
                except Exception:
                    pass
                _notify(name, initial)

                # Vent lidt så listeners er klar, hent derefter media state.
                # update_status() sender en GET_STATUS request — ikke en kommando
                # der afbryder afspilning. Den triggerser new_media_status callback.
                time.sleep(2)
                try:
                    chromecast.media_controller.update_status()
                    log.info("Cast %s: media status opdatering anmodet", name)
                except Exception as e:
                    log.warning("Cast %s: kunne ikke hente media status: %s", name, e)

            except Exception as e:
                log.warning("Cast: kunne ikke forbinde til %s: %s", name, e)
                _notify(name, _empty_state(name))

        def _on_cast(chromecast):
            name = chromecast.name
            log.info("Cast: fandt %s (%s)", name, chromecast.uri)
            _chromecasts[name] = chromecast
            chromecast.register_status_listener(_StatusListener(name))
            chromecast.media_controller.register_status_listener(_MediaListener(name))
            chromecast.register_connection_listener(_ConnectionListener(name, chromecast))
            # Forbind i separat tråd så discovery ikke blokeres
            t = threading.Thread(target=_connect_cast, args=(chromecast,), daemon=True, name=f"cast-connect-{name}")
            t.start()

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
        while not _stop_event.is_set():
            time.sleep(1)

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
