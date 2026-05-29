"""
routers/cast.py — Cast state endpoints + SSE stream
"""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.cast_service import get_state, add_listener, control_device

router        = APIRouter()
router_auth   = APIRouter()  # control endpoints med API-nøgle krav

# ── SSE event queue per forbundet klient ──────────────────────────────────────
_sse_queues: list[asyncio.Queue] = []


def _on_cast_state(device: str, state: dict):
    """Kaldes fra cast_service når state ændrer sig — pusher til alle SSE-klienter."""
    # Publicer også til MQTT
    try:
        from backend.mqtt_client import mqtt_client
        mqtt_client.publish(f"familieoverblik/cast/{device}/state", state, retain=True)
    except Exception:
        pass
    # Push til SSE-klienter
    data = json.dumps(state)
    for q in list(_sse_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


# Registrer listener én gang
add_listener(_on_cast_state)


@router.get("/api/cast/state")
def cast_state():
    """Returnerer seneste state for alle Cast-enheder."""
    return get_state()


@router.get("/api/cast/stream")
async def cast_stream(request: Request):
    """SSE stream — sender state-opdateringer i real-time."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_queues.append(queue)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Send nuværende state straks
            for device, state in get_state().items():
                yield f"data: {json.dumps(state)}\n\n"
            # Herefter stream ændringer
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _sse_queues.remove(queue)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router_auth.post("/api/cast/{device}/pause")
def cast_pause(device: str):
    return {"ok": control_device(device, "pause")}

@router_auth.post("/api/cast/{device}/play")
def cast_play(device: str):
    return {"ok": control_device(device, "play")}

@router_auth.post("/api/cast/{device}/stop")
def cast_stop(device: str):
    return {"ok": control_device(device, "stop")}

@router_auth.post("/api/cast/{device}/next")
def cast_next(device: str):
    return {"ok": control_device(device, "next")}

@router_auth.post("/api/cast/{device}/previous")
def cast_previous(device: str):
    return {"ok": control_device(device, "previous")}

@router_auth.post("/api/cast/{device}/seek")
async def cast_seek(device: str, request: Request):
    data = await request.json()
    delta = float(data.get("delta", 0))
    return {"ok": control_device(device, "seek", delta=delta)}

@router_auth.post("/api/cast/{device}/volume")
async def cast_volume(device: str, request: Request):
    data = await request.json()
    level = float(data.get("level", 0.5))
    return {"ok": control_device(device, "volume", level=level)}
