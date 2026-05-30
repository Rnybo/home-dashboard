"""
backend/cast_service.py — Google Cast / Nest device monitoring
Opdager Cast-enheder via mDNS og abonnerer på media status events.
Publicerer til MQTT: familieoverblik/cast/{device}/state

Baseret på Home Assistant's CastMediaPlayerEntity implementering:
https://github.com/home-assistant/core/blob/dev/homeassistant/components/cast/media_player.py
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
        "device":              name,
        "app":                 None,
        "state":               "IDLE",
        "title":               None,
        "artist":              None,
        "album":               None,
        "image":               None,
        "volume":              None,
        "volume_muted":        False,
        "volume_control_fixed": False,
        "supports_pause":      True,
        "supports_seek":       False,
        "supports_next":       False,
        "supports_previous":   False,
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


# Apps der ikke rapporterer media info pålideligt — samme liste som HA
_UNRELIABLE_MEDIA_INFO_APPS = {"Netflix"}


class _MediaListener:
    """
    Lytter på media status events fra pychromecast.
    Bruger MediaStatus properties direkte — samme som HA's implementering.
    """
    def __init__(self, name: str):
        self.name = name

    def new_media_status(self, status):
        if not status:
            return

        # Log IDLE+ERROR — samme som HA's new_media_status fejlhåndtering
        if status.player_is_idle and status.idle_reason == "ERROR":
            log.warning("Cast %s: media fejl — idle_reason=ERROR content_id=%s",
                        self.name, status.content_id)

        image = None
        if status.images:
            image = status.images[0].url

        with _lock:
            prev = _state.get(self.name) or {}
            current_app    = prev.get("app")
            current_volume = prev.get("volume")
            current_muted  = prev.get("volume_muted", False)
            current_fixed  = prev.get("volume_control_fixed", False)

        # Map UNKNOWN → IDLE — HA filtrerer UNKNOWN fra i state property
        player_state = status.player_state
        if player_state == "UNKNOWN":
            player_state = "IDLE"

        # Marker apps med upålidelig media info — samme som HA's APP_IDS_UNRELIABLE_MEDIA_INFO
        unreliable = any(app in (current_app or "") for app in _UNRELIABLE_MEDIA_INFO_APPS)

        state = {
            "device":              self.name,
            "app":                 current_app,
            "state":               player_state,
            "title":               status.title,
            "artist":              status.artist,
            "album":               status.album_name,
            "image":               image,
            "volume":              current_volume,
            "volume_muted":        current_muted,
            "volume_control_fixed": current_fixed,
            "current_time":        status.adjusted_current_time,
            "duration":            status.duration,
            "last_updated":        time.time(),
            "supports_pause":      status.supports_pause,
            "supports_seek":       status.supports_seek,
            "supports_next":       status.supports_queue_next,
            "supports_previous":   status.supports_queue_prev,
            "unreliable_info":     unreliable,
        }
        log.info("Cast %s: %s — %s af %s", self.name, player_state, status.title, status.artist)
        _notify(self.name, state)

    def load_media_failed(self, queue_item_id: int, error_code: int):
        log.warning("Cast %s: load_media_failed item=%s code=%s", self.name, queue_item_id, error_code)


class _StatusListener:
    """
    Lytter på cast status events (volumen, app navn).
    Bruger chromecast.app_display_name — samme som HA's app_name property.
    """
    def __init__(self, name: str, cc):
        self.name = name
        self._cc = cc  # reference til chromecast for app_display_name

    def new_cast_status(self, status):
        if not status:
            return
        with _lock:
            current = dict(_state.get(self.name, _empty_state(self.name)))

        current["volume"]       = round(status.volume_level, 2) if status.volume_level is not None else None
        current["volume_muted"] = bool(status.volume_muted)
        # VOLUME_CONTROL_TYPE_FIXED = "fixed" — Ref: pychromecast/controllers/receiver.py
        # "attenuation" er VOLUME_CONTROL_TYPE_ATTENUATION (ikke fixed)
        current["volume_control_fixed"] = (getattr(status, "volume_control_type", "") == "fixed")
        try:
            app_name = self._cc.app_display_name
        except Exception:
            app_name = status.display_name
        if app_name:
            current["app"] = app_name

        _notify(self.name, current)


class _ConnectionListener:
    """
    Lytter på forbindelsesstatus.
    Samme adfærd som HA: opdater kun state ved faktisk ændring.
    CONNECTED: log + re-notify eksisterende state så frontend ved enheden er tilbage.
    DISCONNECTED/LOST: nulstil state.
    """
    def __init__(self, name: str, cc):
        self.name = name
        self.cc = cc
        self._was_connected = False

    def new_connection_status(self, status):
        conn = status.status
        log.info("Cast %s forbindelsesstatus: %s", self.name, conn)

        if conn in ("DISCONNECTED", "LOST"):
            if self._was_connected:
                self._was_connected = False
                _notify(self.name, _empty_state(self.name))
        elif conn == "CONNECTED":
            if not self._was_connected:
                self._was_connected = True
                # Re-notify eksisterende state — frontend ved nu at enheden er tilgængelig
                with _lock:
                    current = dict(_state.get(self.name, _empty_state(self.name)))
                _notify(self.name, current)


# ── Offentlig API ──────────────────────────────────────────────────────────────

_chromecasts: dict[str, object] = {}  # name → pychromecast instance


def get_devices() -> list[str]:
    """Returnerer navne på alle kendte Cast-enheder."""
    with _lock:
        return list(_chromecasts.keys())


def get_state() -> dict:
    """Returnerer seneste state for alle opdagede enheder."""
    with _lock:
        return dict(_state)


def add_listener(cb: Callable):
    """Tilføj callback der kaldes ved state-ændring: cb(device, state)."""
    with _lock:
        _listeners.append(cb)


def control_device(device: str, action: str, **kwargs) -> bool:
    """
    Styr en Cast-enhed.
    Tjekker supports_* flags inden kommandoer sendes — samme som HA's supported_features.
    Sender optimistisk state-opdatering straks via WS.
    """
    cc = _chromecasts.get(device)
    if not cc:
        log.warning("control_device: enhed '%s' ikke fundet", device)
        return False
    try:
        mc = cc.media_controller
        ms = mc.status  # MediaStatus objekt

        if action == "play":
            mc.play()
        elif action == "pause":
            if ms and not ms.supports_pause:
                log.warning("Cast %s: pause ikke understøttet", device)
                return False
            mc.pause()
        elif action == "stop":
            mc.stop()
        elif action == "next":
            if not (ms and ms.supports_queue_next):
                log.warning("Cast %s: queue_next ikke understøttet", device)
                return False
            mc.queue_next()
        elif action == "previous":
            if not (ms and ms.supports_queue_prev):
                log.warning("Cast %s: queue_prev ikke understøttet", device)
                return False
            mc.queue_prev()
        elif action == "seek":
            if not (ms and ms.supports_seek):
                log.warning("Cast %s: seek ikke understøttet", device)
                return False
            current = ms.current_time if ms else 0
            mc.seek(max(0, current + float(kwargs.get("delta", 0))))
        elif action == "seek_abs":
            if not (ms and ms.supports_seek):
                return False
            mc.seek(max(0, float(kwargs.get("position", 0))))
        elif action == "volume":
            cc.set_volume(float(kwargs.get("level", 0.5)))
        elif action == "mute":
            cc.set_volume_muted(bool(kwargs.get("muted", True)))

        # Optimistisk state-push — pychromecast sender ikke altid event tilbage
        _push_optimistic(device, action, **kwargs)
        return True
    except Exception as e:
        log.warning("control_device fejl %s %s: %s", device, action, e)
        return False


def _push_optimistic(device: str, action: str, **kwargs):
    """
    Push øjeblikkelig state-opdatering til frontend baseret på kontrol-handling.
    Den rigtige event fra enheden overskriver denne når den ankommer.
    """
    with _lock:
        current = dict(_state.get(device, _empty_state(device)))

    if action == "pause":
        current["state"] = "PAUSED"
    elif action == "play":
        current["state"] = "PLAYING"
    elif action == "stop":
        current["state"] = "IDLE"
        current["title"] = None
        current["artist"] = None
        current["album"] = None
        current["image"] = None
    elif action == "volume":
        current["volume"] = round(float(kwargs.get("level", 0.5)), 2)
    elif action == "mute":
        current["volume_muted"] = bool(kwargs.get("muted", True))
    elif action in ("next", "previous"):
        current["state"] = "BUFFERING"
        current["title"] = None
        current["artist"] = None

    _notify(device, current)


# Spotify Cast App ID — bruges til at wake Nest-enheder
SPOTIFY_CAST_APP_ID = "CC32E753"


def transfer_playback(source: str, target: str, spotify_device_id: str | None = None) -> dict:
    """
    Overfør Spotify-afspilning til target Cast-enhed.
    1. Start Spotify-appen på target via Cast (waker enheden op)
    2. Vent på at Spotify registrerer enheden
    3. Transfer via Spotify Connect API
    """
    src_state = _state.get(source, {})
    app = (src_state.get("app") or "").lower()

    if "spotify" not in app:
        return {"ok": False, "method": "unsupported",
                "detail": f"Transfer understøttes kun for Spotify (app='{src_state.get('app')}')"}

    try:
        from backend.spotify_utils import get_spotify_access_token
        import requests as req
        token = get_spotify_access_token()
        if not token:
            return {"ok": False, "method": "spotify", "detail": "Spotify ikke forbundet"}

        # Brug direkte device ID hvis sendt
        if spotify_device_id:
            r2 = req.put("https://api.spotify.com/v1/me/player",
                         headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json"},
                         json={"device_ids": [spotify_device_id], "play": True}, timeout=8)
            log.info("Spotify transfer (direct id) response: %s", r2.status_code)
            if r2.status_code in (200, 204):
                return {"ok": True, "method": "spotify"}
            return {"ok": False, "method": "spotify",
                    "detail": f"Spotify API {r2.status_code}: {r2.text[:200]}"}

        # Ingen direkte ID — wake target-enheden via Cast og poll Spotify
        tgt_cc = _chromecasts.get(target)
        if tgt_cc:
            try:
                log.info("Spotify transfer: starter Spotify-app på '%s' via Cast", target)
                tgt_cc.start_app(SPOTIFY_CAST_APP_ID)
            except Exception as e:
                log.warning("Cast start_app fejl: %s", e)

        # Poll Spotify i op til 10 sek for at target dukker op
        device_id = None
        for attempt in range(5):
            time.sleep(2)
            r = req.get("https://api.spotify.com/v1/me/player/devices",
                        headers={"Authorization": f"Bearer {token}"}, timeout=8)
            r.raise_for_status()
            devices = r.json().get("devices", [])
            log.info("Spotify poll %d: devices=%s", attempt + 1,
                     [(d["name"], d["id"][:8]) for d in devices])

            # Match target-navn
            tl = target.lower()
            match = next((d for d in devices
                          if tl in d["name"].lower() or d["name"].lower() in tl), None)
            if match:
                device_id = match["id"]
                log.info("Spotify transfer: fandt '%s' efter %d forsøg", match["name"], attempt + 1)
                break

        if not device_id:
            # Fallback: brug første ikke-aktive device
            r = req.get("https://api.spotify.com/v1/me/player/devices",
                        headers={"Authorization": f"Bearer {token}"}, timeout=8)
            devices = r.json().get("devices", [])
            match = next((d for d in devices if not d.get("is_active")), None) or (devices[0] if devices else None)
            if not match:
                return {"ok": False, "method": "spotify",
                        "detail": f"Target '{target}' ikke fundet i Spotify. Tilgængelige: {[d['name'] for d in devices]}"}
            device_id = match["id"]
            log.info("Spotify transfer fallback: bruger '%s'", match["name"])

        r2 = req.put("https://api.spotify.com/v1/me/player",
                     headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json"},
                     json={"device_ids": [device_id], "play": True}, timeout=8)
        log.info("Spotify transfer response: %s", r2.status_code)
        if r2.status_code in (200, 204):
            return {"ok": True, "method": "spotify"}
        return {"ok": False, "method": "spotify",
                "detail": f"Spotify API {r2.status_code}: {r2.text[:200]}"}

    except Exception as e:
        log.exception("Transfer fejl")
        return {"ok": False, "method": "spotify", "detail": str(e)}


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
    """Start Cast discovery og monitoring i baggrundstråd."""
    if not _CAST_AVAILABLE:
        log.warning("pychromecast ikke tilgængeligt — Cast deaktiveret")
        return
    _stop_event.clear()
    t = threading.Thread(target=_run, args=(known_hosts,), daemon=True, name="cast-service")
    t.start()
    log.info("Cast service startet")


def _connect_cast(chromecast):
    """
    Forbind til enhed og sæt initial state.
    pychromecast kalder automatisk channel_connected → update_status() → new_media_status().
    Vi sætter kun en initial IDLE state med volumen fra cast_status.
    """
    name = chromecast.name
    try:
        chromecast.wait(timeout=10)
        initial = _empty_state(name)
        try:
            s = chromecast.status
            if s:
                initial["volume"] = round(s.volume_level, 2) if s.volume_level is not None else None
                initial["app"]    = chromecast.app_display_name or None
                initial["volume_muted"] = bool(s.volume_muted)
                initial["volume_control_fixed"] = (getattr(s, "volume_control_type", "") == "fixed")
        except Exception:
            pass
        _notify(name, initial)
        # new_media_status ankommer automatisk via channel_connected — ingen polling nødvendig
    except Exception as e:
        log.warning("Cast: kunne ikke forbinde til %s: %s", name, e)
        _notify(name, _empty_state(name))


def _run(known_hosts: list[str] | None):
    browser = None
    try:
        import zeroconf as zc_module

        def _on_cast(chromecast):
            name = chromecast.name
            log.info("Cast: fandt %s (%s)", name, chromecast.uri)
            _chromecasts[name] = chromecast
            chromecast.register_status_listener(_StatusListener(name, chromecast))
            chromecast.media_controller.register_status_listener(_MediaListener(name))
            chromecast.register_connection_listener(_ConnectionListener(name, chromecast))
            t = threading.Thread(target=_connect_cast, args=(chromecast,),
                                 daemon=True, name=f"cast-connect-{name}")
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
        print(f"  App: {state['app']}, Vol: {state['volume']}, next={state['supports_next']}")

    add_listener(on_state)
    start()

    print("Lytter efter Cast-enheder — tryk Ctrl+C for at stoppe")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
