"""Shared async stream handler for the three demo modes.

The handler is mode-agnostic. Each `app_*.py` builds it by supplying:
  * a `connect_factory` callable that returns the async context manager for the
    OpenAI Realtime connection (this *is* the per-rung diff), and
  * a `make_session` callable that returns the session config dict to send via
    `conn.session.update(session=...)`.

The handler then takes care of the audio pipe, transcript fan-out, status
events, and reconnect-on-voice-change concerns.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

import gradio as gr
import numpy as np
from fastrtc import AdditionalOutputs, AsyncStreamHandler, wait_for_item

if TYPE_CHECKING:
    from voicelive_demo.config import Mode

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000

ConnectFactory = Callable[[], Awaitable[AbstractAsyncContextManager[Any]]]
SessionFactory = Callable[["SharedState"], dict]


@dataclass
class SharedState:
    """Mutable state that flows from the UI into the handler.

    Lives at module scope per app so the Gradio UI can mutate it (voice picker,
    reset button) and the running handler picks the change up on the next
    `session.update`.
    """

    mode: "Mode | None" = None
    locale: str = "en"
    voice: str = "en-US-Ava:DragonHDLatestNeural"
    voice_type: str = "azure-standard"
    instructions: str = (
        "You are a friendly, concise voice assistant. Keep replies short — under 2 sentences "
        "unless the user explicitly asks for more. Speak naturally."
    )
    reset_requested: bool = False
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StatusEvent:
    """A discriminated payload pushed into the chatbot's AdditionalOutputs stream."""

    kind: str  # "status" | "message" | "session"
    payload: dict


class VoiceHandler(AsyncStreamHandler):
    """Pipes microphone audio into the Realtime connection and streams the model's audio back."""

    def __init__(
        self,
        *,
        name: str,
        connect_factory: ConnectFactory,
        make_session: SessionFactory,
        shared: SharedState,
    ) -> None:
        super().__init__(
            expected_layout="mono",
            output_sample_rate=SAMPLE_RATE,
            input_sample_rate=SAMPLE_RATE,
        )
        self.name = name
        self.connect_factory = connect_factory
        self.make_session = make_session
        self.shared = shared
        self.connection: Optional[Any] = None
        self.output_queue: asyncio.Queue = asyncio.Queue()

    def copy(self) -> "VoiceHandler":
        return VoiceHandler(
            name=self.name,
            connect_factory=self.connect_factory,
            make_session=self.make_session,
            shared=self.shared,
        )

    async def _push_status(self, status: str) -> None:
        await self.output_queue.put(AdditionalOutputs(StatusEvent("status", {"status": status})))

    async def _push_message(self, role: str, content: str) -> None:
        await self.output_queue.put(
            AdditionalOutputs(StatusEvent("message", {"role": role, "content": content}))
        )

    async def _push_session(self, session_id: str, model: str) -> None:
        await self.output_queue.put(
            AdditionalOutputs(StatusEvent("session", {"session_id": session_id, "model": model}))
        )

    async def start_up(self) -> None:
        logger.info("[%s] starting up", self.name)
        await self._push_status("connecting")
        try:
            conn_mgr = await self.connect_factory()
            async with conn_mgr as conn:
                self.connection = conn
                session = self.make_session(self.shared)
                await conn.session.update(session=session)
                logger.info("[%s] session.update sent", self.name)
                await self._push_status("idle")
                async for event in conn:
                    await self._handle_event(event)
        except Exception:
            logger.exception("[%s] connection died", self.name)
            await self._push_status("error")

    async def _handle_event(self, event: Any) -> None:
        etype = getattr(event, "type", "?")
        logger.debug("[%s] %s", self.name, etype)

        if etype == "session.created":
            sess = getattr(event, "session", None)
            sid = getattr(sess, "id", "?") if sess else "?"
            model = getattr(sess, "model", "?") if sess else "?"
            logger.info("[%s] session %s ready (model=%s)", self.name, sid, model)
            await self._push_session(sid, model)

        elif etype == "input_audio_buffer.speech_started":
            self.clear_queue()
            await self._push_status("listening")

        elif etype == "input_audio_buffer.speech_stopped":
            await self._push_status("thinking")

        elif etype == "conversation.item.input_audio_transcription.completed":
            transcript = getattr(event, "transcript", "")
            if transcript:
                await self._push_message("user", transcript)

        # Cover both preview event names (response.audio.*) and the GA names
        # (response.output_audio.*) so we stay compatible across SDK versions.
        elif etype in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
            transcript = getattr(event, "transcript", "")
            if transcript:
                await self._push_message("assistant", transcript)

        elif etype in ("response.audio.delta", "response.output_audio.delta"):
            delta = getattr(event, "delta", None)
            if delta:
                await self._push_status("speaking")
                audio = np.frombuffer(base64.b64decode(delta), dtype=np.int16).reshape(1, -1)
                await self.output_queue.put((self.output_sample_rate, audio))

        elif etype in ("response.done", "response.audio.done", "response.output_audio.done"):
            await self._push_status("idle")

        elif etype == "error":
            err = getattr(event, "error", None)
            msg = getattr(err, "message", str(err)) if err else "unknown error"
            logger.error("[%s] server error: %s", self.name, msg)
            await self._push_message("assistant", f"⚠️ server error: {msg}")
            await self._push_status("error")

    async def receive(self, frame: tuple[int, np.ndarray]) -> None:
        if not self.connection:
            return
        _, array = frame
        array = array.squeeze()
        audio_message = base64.b64encode(array.tobytes()).decode("utf-8")
        try:
            await self.connection.input_audio_buffer.append(audio=audio_message)  # type: ignore[attr-defined]
        except Exception:
            logger.exception("[%s] failed to forward frame", self.name)

    async def emit(self) -> tuple[int, np.ndarray] | AdditionalOutputs | None:
        return await wait_for_item(self.output_queue)

    async def shutdown(self) -> None:
        if self.connection:
            try:
                await self.connection.close()
            except Exception:
                logger.exception("[%s] error during shutdown", self.name)
            finally:
                self.connection = None


# Awaitable type hint convenience for app_*.py
AsyncCallable = Callable[..., Awaitable[Any]]
_ = gr  # keep gradio import for downstream re-exports / typing
