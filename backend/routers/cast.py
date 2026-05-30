"""
routers/cast.py — Cast state endpoints + WebSocket stream
"""
import asyncio
import json
import random
import threading
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException

from backend.cast_service import get_state, get_devices, add_listener, control_device, transfer_playback

router      = APIRouter()
router_auth = APIRouter()

# ── WebSocket queues ───────────────────────────────────────────────────────────
_ws_queues: list[asyncio.Queue] = []


def _on_cast_state(device: str, state: dict):
    try:
        from backend.mqtt_client import mqtt_client
        mqtt_client.publish(f"familieoverblik/cast/{device}/state", state, retain=True)
    except Exception:
        pass
    data = json.dumps(state)
    for q in list(_ws_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


add_listener(_on_cast_state)

# ── Mock ───────────────────────────────────────────────────────────────────────
_MOCK_TRACKS = [
    {"title": "Blinding Lights",   "artist": "The Weeknd",    "album": "After Hours",          "image": "https://i.scdn.co/image/ab67616d0000b273ef017e899c0547766997d874"},
    {"title": "Bohemian Rhapsody", "artist": "Queen",         "album": "A Night at the Opera",  "image": None},
    {"title": "As It Was",         "artist": "Harry Styles",  "album": "Harry's House",         "image": "https://i.scdn.co/image/ab67616d0000b2736522b40a8c5ef9df7e75d982"},
    {"title": "Levitating",        "artist": "Dua Lipa",      "album": "Future Nostalgia",      "image": "https://i.scdn.co/image/ab67616d0000b2734bc66095f8a70bc4e6593f4f"},
    {"title": "Heat Waves",        "artist": "Glass Animals", "album": "Dreamland",             "image": None},
]

_MOCK_DEVICES: dict[str, dict] = {
    "Stuen":      {"app": "Spotify",       "state": "PLAYING", "volume": 0.45, "track_idx": 0},
    "Køkken Hub": {"app": "YouTube Music", "state": "PAUSED",  "volume": 0.60, "track_idx": 1},
    "Speakers":   {"app": "Spotify",       "state": "IDLE",    "volume": 0.50, "track_idx": 2},
}

_mock_thread: threading.Thread | None = None
_mock_loop:   asyncio.AbstractEventLoop | None = None


def _build_mock(name: str, dev: dict) -> dict:
    t = _MOCK_TRACKS[dev["track_idx"] % len(_MOCK_TRACKS)]
    active = dev["state"] in ("PLAYING", "BUFFERING", "PAUSED")
    return {
        "device": name,
        "app":    dev["app"]    if active else None,
        "state":  dev["state"],
        "title":  t["title"]   if active else None,
        "artist": t["artist"]  if active else None,
        "album":  t["album"]   if active else None,
        "image":  t["image"]   if active else None,
        "volume": dev["volume"],
    }


def _push(name: str):
    data = json.dumps(_build_mock(name, _MOCK_DEVICES[name]))
    if _mock_loop and not _mock_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(data), _mock_loop)


async def _broadcast(data: str):
    for q in list(_ws_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


_mock_lock = threading.Lock()


def _mock_simulate():
    """Simulerer sang-skift og pause-toggle hvert 8. sekund."""
    while True:
        time.sleep(8)
        with _mock_lock:
            # Stuen: næste sang — kun hvis faktisk PLAYING
            dev = _MOCK_DEVICES["Stuen"]
            if dev["state"] == "PLAYING":
                dev["track_idx"] += 1
                _push("Stuen")
            # Køkken Hub: toggle kun hvis ikke manuelt styret — reset til PLAYING/PAUSED
            dev2 = _MOCK_DEVICES["Køkken Hub"]
            if dev2["state"] == "PLAYING":
                dev2["state"] = "PAUSED"
                _push("Køkken Hub")
            elif dev2["state"] == "PAUSED":
                dev2["state"] = "PLAYING"
                _push("Køkken Hub")


def _mock_control(device: str, action: str, **kwargs):
    """Håndter kontrol-handlinger på mock-enheder."""
    if device not in _MOCK_DEVICES:
        return
    with _mock_lock:
        dev = _MOCK_DEVICES[device]
        if action == "pause":
            dev["state"] = "PAUSED"
        elif action == "play":
            dev["state"] = "PLAYING"
        elif action == "stop":
            dev["state"] = "IDLE"
        elif action == "next":
            dev["track_idx"] += 1
            dev["state"] = "PLAYING"
        elif action == "previous":
            dev["track_idx"] = max(0, dev["track_idx"] - 1)
            dev["state"] = "PLAYING"
        elif action == "volume":
            dev["volume"] = round(float(kwargs.get("level", 0.5)), 2)
    _push(device)


def _mock_transfer(source: str, target: str):
    """Flyt afspilning fra source til target i mock."""
    src = _MOCK_DEVICES.get(source)
    tgt = _MOCK_DEVICES.get(target)
    if not src or not tgt:
        return
    tgt["state"]     = "PLAYING"
    tgt["track_idx"] = src["track_idx"]
    tgt["app"]       = src["app"]
    src["state"]     = "IDLE"
    _push(source)
    _push(target)


def _is_mock() -> bool:
    import os
    return os.getenv("CAST_MOCK", "").lower() in ("1", "true", "yes")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/cast/state")
def cast_state():
    if _is_mock():
        return {n: _build_mock(n, d) for n, d in _MOCK_DEVICES.items()}
    return get_state()


@router.get("/api/cast/devices")
def cast_devices():
    if _is_mock():
        return {"devices": list(_MOCK_DEVICES.keys())}
    return {"devices": get_devices()}


@router.websocket("/ws/cast")
async def cast_ws(websocket: WebSocket):
    global _mock_thread, _mock_loop
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _ws_queues.append(queue)

    # Start mock simulator første gang
    if _is_mock():
        _mock_loop = asyncio.get_event_loop()
        if _mock_thread is None or not _mock_thread.is_alive():
            _mock_thread = threading.Thread(target=_mock_simulate, daemon=True, name="cast-mock")
            _mock_thread.start()
        # Send initial mock state
        for name, dev in _MOCK_DEVICES.items():
            await websocket.send_text(json.dumps(_build_mock(name, dev)))
    else:
        for state in get_state().values():
            await websocket.send_text(json.dumps(state))

    try:
        while True:
            data = await asyncio.wait_for(queue.get(), timeout=30)
            await websocket.send_text(data)
    except (WebSocketDisconnect, asyncio.TimeoutError, Exception):
        pass
    finally:
        _ws_queues.remove(queue)


@router_auth.post("/api/cast/{device}/transfer")
async def cast_transfer_ep(device: str, request: Request):
    data = await request.json()
    target = data.get("target", "")
    spotify_device_id = data.get("spotify_device_id")
    if not target:
        raise HTTPException(400, "target required")
    if _is_mock():
        _mock_transfer(device, target)
        return {"ok": True, "method": "mock"}
    # Kør i thread så polling ikke blokerer event loop
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: transfer_playback(device, target, spotify_device_id)
    )
    return result


@router_auth.post("/api/cast/{device}/pause")
def cast_pause(device: str):
    if _is_mock(): _mock_control(device, "pause"); return {"ok": True}
    return {"ok": control_device(device, "pause")}

@router_auth.post("/api/cast/{device}/play")
def cast_play(device: str):
    if _is_mock(): _mock_control(device, "play"); return {"ok": True}
    return {"ok": control_device(device, "play")}

@router_auth.post("/api/cast/{device}/stop")
def cast_stop(device: str):
    if _is_mock(): _mock_control(device, "stop"); return {"ok": True}
    return {"ok": control_device(device, "stop")}

@router_auth.post("/api/cast/{device}/next")
def cast_next(device: str):
    if _is_mock(): _mock_control(device, "next"); return {"ok": True}
    return {"ok": control_device(device, "next")}

@router_auth.post("/api/cast/{device}/previous")
def cast_previous(device: str):
    if _is_mock(): _mock_control(device, "previous"); return {"ok": True}
    return {"ok": control_device(device, "previous")}

@router_auth.post("/api/cast/{device}/seek")
async def cast_seek(device: str, request: Request):
    data = await request.json()
    delta = float(data.get("delta", 0))
    if _is_mock(): return {"ok": True}
    return {"ok": control_device(device, "seek", delta=delta)}

@router_auth.post("/api/cast/{device}/seek_abs")
async def cast_seek_abs(device: str, request: Request):
    """Seek til absolut position i sekunder."""
    data = await request.json()
    position = float(data.get("position", 0))
    if _is_mock(): return {"ok": True}
    return {"ok": control_device(device, "seek_abs", position=position)}

@router_auth.post("/api/cast/{device}/mute")
async def cast_mute(device: str, request: Request):
    data = await request.json()
    muted = bool(data.get("muted", True))
    if _is_mock(): _mock_control(device, "mute", muted=muted); return {"ok": True}
    return {"ok": control_device(device, "mute", muted=muted)}

@router_auth.post("/api/cast/{device}/volume")
async def cast_volume(device: str, request: Request):
    data = await request.json()
    level = float(data.get("level", 0.5))
    if _is_mock(): _mock_control(device, "volume", level=level); return {"ok": True}
    return {"ok": control_device(device, "volume", level=level)}
