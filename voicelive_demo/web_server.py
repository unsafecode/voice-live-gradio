"""FastAPI + WebSocket shell — the deployable variant of the demo.

Same three rungs, same handler contracts, no Gradio and no WebRTC.
Audio is plain 24 kHz PCM16 over a regular WebSocket, which means
this app runs cleanly on any L7-only container platform (ACA,
App Service, Cloud Run, …) without a TURN server.

Protocol on the ``/ws/{rung}`` WebSocket:

* **Browser → server**
    * binary frames  — raw 24 kHz mono PCM16 audio
    * JSON text      — control: ``{"type": "config", "voice": "...",
                                   "instructions": "...", "locale": "en"}``

* **Server → browser**
    * binary frames  — raw 24 kHz mono PCM16 audio (model output)
    * JSON text      — events:
        - ``{"type": "status", "status": "connecting|idle|listening|thinking|speaking|error"}``
        - ``{"type": "message", "role": "user|assistant", "content": "..."}``
        - ``{"type": "session", "session_id": "...", "model": "..."}``
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from voicelive_demo.config import Mode, get_settings
from voicelive_demo.handler import SharedState
from voicelive_demo.i18n import (
    DEFAULT_VOICE,
    LOCALES,
    REALTIME_DEFAULT_VOICE,
    REALTIME_VOICE_OPTIONS,
    VOICE_OPTIONS,
)
from voicelive_demo.rungs import agent as agent_rung
from voicelive_demo.rungs import realtime as realtime_rung
from voicelive_demo.rungs import voicelive as voicelive_rung

logger = logging.getLogger("voicelive_demo.web")

# ── Static assets shipped alongside the package ──────────────────────────
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# ── Per-rung wiring (mirrors app_*.py) ───────────────────────────────────
ConnectFactory = Callable[..., AbstractAsyncContextManager[Any]]
SessionFactory = Callable[[SharedState], dict]

_RUNGS: dict[str, tuple[ConnectFactory, SessionFactory]] = {
    "realtime":  (realtime_rung.connect_factory,  realtime_rung.make_session),
    "voicelive": (voicelive_rung.connect_factory, voicelive_rung.make_session),
    "agent":     (agent_rung.connect_factory,     agent_rung.make_session),
}


def _available_rungs() -> list[str]:
    """Filter the agent rung out if AGENT_ID / AGENT_PROJECT_NAME are unset."""
    s = get_settings()
    out = ["realtime", "voicelive"]
    if s.agent_id and s.agent_project_name:
        out.append("agent")
    return out


def create_app() -> FastAPI:
    app = FastAPI(title="voice-live-gradio (web)", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/config")
    async def api_config() -> dict:
        s = get_settings()

        def _voices(opts):
            return [{"label": lbl, "name": n, "type": t} for (lbl, n, t) in opts]

        return {
            "rungs": _available_rungs(),
            "default_rung": s.mode.value if s.mode in (Mode.REALTIME, Mode.VOICELIVE, Mode.AGENT) else "voicelive",
            "locales": [{"label": label, "code": code} for (label, code) in LOCALES],
            "default_locale": "en",
            # Voice Live + Foundry Agent rungs share the Azure Neural / HD catalog.
            "azure_voices": {loc: _voices(opts) for loc, opts in VOICE_OPTIONS.items()},
            "default_azure_voice": {
                loc: {"name": name, "type": vtype} for loc, (name, vtype) in DEFAULT_VOICE.items()
            },
            # Realtime rung is locked to the OpenAI voice set (no Azure HD).
            "openai_voices": _voices(REALTIME_VOICE_OPTIONS),
            "default_openai_voice": {
                "name": REALTIME_DEFAULT_VOICE[0], "type": REALTIME_DEFAULT_VOICE[1],
            },
        }

    @app.websocket("/ws/{rung}")
    async def ws_endpoint(websocket: WebSocket, rung: str) -> None:
        if rung not in _RUNGS:
            await websocket.close(code=4400, reason=f"unknown rung: {rung}")
            return
        if rung not in _available_rungs():
            await websocket.close(code=4400, reason=f"rung {rung!r} is not configured on this deployment")
            return

        await websocket.accept()
        connect_factory, make_session = _RUNGS[rung]
        shared = SharedState(locale="en")

        # First text frame can override defaults before we open the upstream session
        try:
            first = await asyncio.wait_for(websocket.receive(), timeout=5.0)
        except asyncio.TimeoutError:
            await websocket.close(code=4408, reason="no config received within 5s")
            return

        if first.get("type") == "websocket.disconnect":
            return
        if first.get("text"):
            try:
                cfg = json.loads(first["text"])
                if cfg.get("type") == "config":
                    shared.voice = cfg.get("voice", shared.voice)
                    shared.voice_type = cfg.get("voice_type", shared.voice_type)
                    shared.locale = cfg.get("locale", shared.locale)
                    instr = cfg.get("instructions")
                    if instr:
                        shared.instructions = instr
            except json.JSONDecodeError:
                logger.warning("bad initial JSON; ignoring")

        await _send_json(websocket, {"type": "status", "status": "connecting"})

        try:
            async with connect_factory() as conn:
                session = make_session(shared)
                await conn.session.update(session=session)
                logger.info("[%s] session.update sent", rung)
                await _send_json(websocket, {"type": "status", "status": "idle"})

                upstream_task = asyncio.create_task(_pump_upstream(conn, websocket, rung))
                browser_task = asyncio.create_task(_pump_browser(conn, websocket, rung))
                done, pending = await asyncio.wait(
                    {upstream_task, browser_task}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
                # surface any exception from the completed task
                for t in done:
                    exc = t.exception()
                    if exc and not isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                        logger.exception("[%s] task failed", rung, exc_info=exc)
        except WebSocketDisconnect:
            logger.info("[%s] browser disconnected", rung)
        except Exception:
            logger.exception("[%s] session died", rung)
            await _send_json(websocket, {"type": "status", "status": "error"})

    # SPA / static — mount LAST so /api and /ws take precedence
    if WEB_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")
    else:
        @app.get("/")
        async def index_missing() -> dict:
            return {"error": f"web assets not found at {WEB_DIR}"}

    return app


async def _send_json(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_text(json.dumps(payload, separators=(",", ":")))
    except (WebSocketDisconnect, RuntimeError):
        pass


async def _pump_browser(conn: Any, websocket: WebSocket, rung: str) -> None:
    """Browser → upstream: forward PCM16 audio + control messages."""
    while True:
        msg = await websocket.receive()
        if msg["type"] == "websocket.disconnect":
            return
        if msg.get("bytes") is not None:
            data: bytes = msg["bytes"]
            if not data:
                continue
            await conn.input_audio_buffer.append(audio=base64.b64encode(data).decode())
        elif msg.get("text") is not None:
            try:
                payload = json.loads(msg["text"])
            except json.JSONDecodeError:
                continue
            kind = payload.get("type")
            if kind == "ping":
                await _send_json(websocket, {"type": "pong"})


async def _pump_upstream(conn: Any, websocket: WebSocket, rung: str) -> None:
    """Upstream → browser: forward audio chunks + status / transcript events.

    Mirrors ``voicelive_demo/handler.py._handle_event`` but emits JSON / raw
    PCM frames over the FastAPI WebSocket instead of FastRTC AdditionalOutputs.
    """
    async for event in conn:
        etype = getattr(event, "type", "?")

        if etype == "session.created":
            sess = getattr(event, "session", None)
            sid = getattr(sess, "id", "?") if sess else "?"
            model = getattr(sess, "model", "?") if sess else "?"
            logger.info("[%s] session %s ready (model=%s)", rung, sid, model)
            await _send_json(websocket, {"type": "session", "session_id": sid, "model": model})

        elif etype == "input_audio_buffer.speech_started":
            await _send_json(websocket, {"type": "status", "status": "listening"})
            await _send_json(websocket, {"type": "clear_playback"})

        elif etype == "input_audio_buffer.speech_stopped":
            await _send_json(websocket, {"type": "status", "status": "thinking"})

        elif etype == "conversation.item.input_audio_transcription.completed":
            transcript = getattr(event, "transcript", "")
            if transcript:
                await _send_json(websocket, {"type": "message", "role": "user", "content": transcript})

        elif etype in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
            transcript = getattr(event, "transcript", "")
            if transcript:
                await _send_json(websocket, {"type": "message", "role": "assistant", "content": transcript})

        elif etype in ("response.audio.delta", "response.output_audio.delta"):
            delta = getattr(event, "delta", None)
            if delta:
                await _send_json(websocket, {"type": "status", "status": "speaking"})
                await websocket.send_bytes(base64.b64decode(delta))

        elif etype in ("response.done", "response.audio.done", "response.output_audio.done"):
            await _send_json(websocket, {"type": "status", "status": "idle"})

        elif etype == "error":
            err = getattr(event, "error", None)
            msg = getattr(err, "message", str(err)) if err else "unknown error"
            logger.error("[%s] server error: %s", rung, msg)
            await _send_json(websocket, {"type": "message", "role": "assistant", "content": f"⚠️ {msg}"})
            await _send_json(websocket, {"type": "status", "status": "error"})


