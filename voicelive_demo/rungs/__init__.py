"""Per-rung registry — single source of truth for the three connection variants.

Each rung is a tiny module that exports:
  * ``connect_factory()``  — async, returns the realtime context manager.
  * ``make_session(shared)`` — returns the session dict.

This package lets:
  * the three ``app_*.py`` shells stay tiny (they just import their rung);
  * the unified ``app_demo.py`` register all rungs and swap between them at
    runtime;
  * the **Switch diff** tab read the source straight from these files —
    so the diff page is always in sync with what the app actually runs.
"""
from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Callable

from voicelive_demo.config import Mode
from voicelive_demo.handler import SharedState
from voicelive_demo.rungs import agent as _agent
from voicelive_demo.rungs import realtime as _realtime
from voicelive_demo.rungs import voicelive as _voicelive


@dataclass(frozen=True)
class Rung:
    mode: Mode
    label: str
    short: str
    color: str
    blurb: str
    # ``connect_factory`` is a sync callable that returns an async context
    # manager (it's decorated with ``@asynccontextmanager``). Accepts an
    # optional ``model=`` keyword so the benchmark can override the deployment
    # without forking the connection logic.
    connect_factory: Callable[..., AbstractAsyncContextManager[Any]]
    make_session: Callable[[SharedState], dict]


REGISTRY: dict[Mode, Rung] = {
    Mode.REALTIME: Rung(
        mode=Mode.REALTIME,
        label="Azure OpenAI Realtime",
        short="Realtime",
        color="#0078D4",
        blurb="Direct GA Realtime API. OpenAI voices. The before.",
        connect_factory=_realtime.connect_factory,
        make_session=_realtime.make_session,
    ),
    Mode.VOICELIVE: Rung(
        mode=Mode.VOICELIVE,
        label="Azure Voice Live",
        short="Voice Live",
        color="#107C10",
        blurb="Same SDK, three small kwargs. Azure Neural HD voices, semantic VAD, server-side echo cancel & noise reduction.",
        connect_factory=_voicelive.connect_factory,
        make_session=_voicelive.make_session,
    ),
    Mode.AGENT: Rung(
        mode=Mode.AGENT,
        label="Voice Live + Foundry Agent",
        short="+ Agent",
        color="#7719AA",
        blurb="Same connect call, agent triplet in extra_query. The hosted agent owns instructions & tools.",
        connect_factory=_agent.connect_factory,
        make_session=_agent.make_session,
    ),
}


__all__ = ["REGISTRY", "Rung"]
