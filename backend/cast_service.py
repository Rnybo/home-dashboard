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
        "device":             name,
        "app":                None,
        "state":              "IDLE",
        "title":              None,
        "artist":             None,
        "album":              None,
        "image":              None,
        "volume":             None,
        "supports_pause":     True,
        "supports_seek":      False,
        "supports_next":      False,
        "supports_previous":  False,
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
    """
    Lytter på media status events fra pychromecast.
    Bruger MediaStatus properties direkte — samme som HA's implementering.
    new_media_status() kaldes automatisk af pychromecast via channel_connected → update_status().
    """
    def __init__(self, name: str):
        self.name = name

    def new_media_status(self, status):
        if not status:
            return

        # Brug MediaStatus properties — ikke rå dict-lookup (kan returnere None/tal)
        # Ref: pychromecast/controllers/media.py MediaStatus properties
        image = None
        if status.images:
            image = status.images[0].url  # MediaImage.url property

        with _lock:
            current_app = (_state.get(self.name) or {}).get("app")

        state = {
            "device":            self.name,
            "app":               current_app,  # bevar app-navn fra _StatusListener
            "state":             status.player_state,  # PLAYING, PAUSED, IDLE, BUFFERING, UNKNOWN
            "title":             status.title,
            "artist":            status.artist,
            "album":             status.album_name,
            "image":             image,
            "volume":            None,  # volumen kommer fra _StatusListener
            # Capabilities — hvad enheden understøtter lige nu
            "supports_pause":    status.supports_pause,
            "supports_seek":     status.supports_seek,
            "supports_next":     status.supports_queue_next,
            "supports_previous": status.supports_queue_prev,
        }
        log.info("Cast %s: %s — %s af %s", self.name, status.player_state, status.title, status.artist)
        _notify(self.name, state)

    def load_media_failed(self, queue_item_id: int, error_code: int):
        log.warning("Cast %s: load_media_failed item=%s code=%s", self.name, queue_item_id, error_code)


class _StatusListener:
    """
    Lytter på cast status events (volumen, app navn).
    Opdaterer volume og app på eksisterende state uden at overskrive media info.
    """
    def __init__(self, name: str):
        self.name = name

    def new_cast_status(self, status):
        if not status:
            return
        with _lock:
            current = dict(_state.get(self.name, _empty_state(self.name)))

        # Bevar media info — opdater kun volumen og app navn
        current["volume"] = round(status.volume_level, 2) if status.volume_level is not None else None
        # app_display_name er det korrekte felt — samme som HA's app_name property
        if status.display_name:
            current["app"] = status.display_name

        _notify(self.name, current)


class _ConnectionListener:
    """
    Lytter på forbindelsesstatus.
    CONNECTED: intet — media status ankommer automatisk via channel_connected → update_status()
    DISCONNECTED/LOST: nulstil state
    """
    def __init__(self, name: str, cc):
        self.name = name
        self.cc = cc

    def new_connection_status(self, status):
        log.info("Cast %s forbindelsesstatus: %s", self.name, status.status)
        if status.status in ("DISCONNECTED", "LOST"):
            _notify(self.name, _empty_state(self.name))


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
        elif action == "volume":
            cc.set_volume(float(kwargs.get("level", 0.5)))

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
    elif action in ("next", "previous"):
        current["state"] = "BUFFERING"
        current["title"] = None
        current["artist"] = None

    _notify(device, current)


def transfer_playback(source: str, target: str, spotify_device_id: str | None = None) -> dict:
    """
    Overfør afspilning fra source til target.
    Spotify: via Spotify Connect API — bruger spotify_device_id hvis angivet, ellers fuzzy match på navn.
    Andre: stop source, start play_media på target.
    """
    src_state = _state.get(source, {})
    app = (src_state.get("app") or "").lower()

    # ── Spotify Connect ───────────────────────────────────────────────────────
    if "spotify" in app:
        try:
            from backend.spotify_utils import get_spotify_access_token
            import requests as req
            token = get_spotify_access_token()
            if not token:
                return {"ok": False, "method": "spotify", "detail": "Spotify ikke forbundet"}

            # Brug direkte device ID hvis vi har det (fra /api/spotify/devices)
            device_id = spotify_device_id
            device_name = target

            if not device_id:
                # Fuzzy match på navn som fallback
                r = req.get("https://api.spotify.com/v1/me/player/devices",
                            headers={"Authorization": f"Bearer {token}"}, timeout=8)
                r.raise_for_status()
                devices = r.json().get("devices", [])
                target_lower = target.lower()
                match = next(
                    (d for d in devices if target_lower in d["name"].lower() or d["name"].lower() in target_lower),
                    None
                )
                if not match:
                    return {"ok": False, "method": "spotify",
                            "detail": f"Ingen Spotify-enhed matcher '{target}'. Fandt: {[d['name'] for d in devices]}"}
                device_id   = match["id"]
                device_name = match["name"]

            r2 = req.put("https://api.spotify.com/v1/me/player",
                         headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                         json={"device_ids": [device_id], "play": True}, timeout=8)
            if r2.status_code in (200, 204):
                return {"ok": True, "method": "spotify", "detail": device_name}
            return {"ok": False, "method": "spotify", "detail": f"Spotify API fejl {r2.status_code}: {r2.text}"}
        except Exception as e:
            return {"ok": False, "method": "spotify", "detail": str(e)}

    # ── Direkte media URL ─────────────────────────────────────────────────────
    src_cc = _chromecasts.get(source)
    tgt_cc = _chromecasts.get(target)
    if not src_cc or not tgt_cc:
        return {"ok": False, "method": "media", "detail": "Enhed ikke fundet"}
    try:
        mc = src_cc.media_controller
        ms = mc.status
        if not ms or not ms.content_id:
            return {"ok": False, "method": "media", "detail": "Ingen aktiv media URL på kildeenhed"}
        url          = ms.content_id
        content_type = ms.content_type or "video/mp4"
        position     = ms.current_time or 0

        src_cc.media_controller.stop()
        tgt_cc.wait(timeout=5)
        tgt_cc.media_controller.play_media(url, content_type, current_time=position)
        return {"ok": True, "method": "media", "detail": target}
    except Exception as e:
        return {"ok": False, "method": "media", "detail": str(e)}


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
    Forbind til enhed og registrer listeners.
    pychromecast kalder automatisk channel_connected → update_status() → new_media_status()
    så vi behøver ikke kalde update_status() manuelt (det afbryder afspilning).
    Vi venter kun på at status-objektet er klar og sender en initial state.
    """
    name = chromecast.name
    try:
        chromecast.wait(timeout=10)

        # Læs initial cast status (volumen, app navn) — ingen netværkskald
        initial = _empty_state(name)
        try:
            s = chromecast.status
            if s:
                initial["volume"] = round(s.volume_level, 2) if s.volume_level is not None else None
                initial["app"]    = s.display_name or None
        except Exception:
            pass
        _notify(name, initial)

        # pychromecast sender new_media_status automatisk via channel_connected.
        # Vi venter op til 5s og læser cached status — UDEN at kalde update_status()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                ms = chromecast.media_controller.status
                if ms and ms.player_state not in ("UNKNOWN", "IDLE", None):
                    log.info("Cast %s: opstartsstate=%s title=%s", name, ms.player_state, ms.title)
                    break
            except Exception:
                pass
            time.sleep(0.5)

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
            chromecast.register_status_listener(_StatusListener(name))
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
