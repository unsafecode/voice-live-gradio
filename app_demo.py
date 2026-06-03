"""Unified switcher — boots one UI that can flip between all three rungs.

This is the demo entry point ``app.py`` defaults to. It registers every
rung whose settings are present (Realtime + Voice Live always; Agent only
when ``AGENT_ID`` + ``AGENT_PROJECT_NAME`` are populated) and lets the user
swap between them at runtime from a segmented control in the header.

Switching modes mutates the handler's ``connect_factory`` and
``make_session`` callables in place — the next time the user clicks the
mic, the new rung's WebSocket destination is dialled. No restart needed.
"""
from __future__ import annotations

import asyncio
import logging

from voicelive_demo.config import Mode, get_settings
from voicelive_demo.handler import SharedState, VoiceHandler
from voicelive_demo.rtc import fetch_acs_turn_config
from voicelive_demo.rungs import REGISTRY
from voicelive_demo.ui import build_ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
_settings = get_settings()
_rtc_configuration = asyncio.run(fetch_acs_turn_config())

_AVAILABLE: list[Mode] = [Mode.REALTIME, Mode.VOICELIVE]
if _settings.agent_id and _settings.agent_project_name:
    _AVAILABLE.append(Mode.AGENT)
else:
    logging.getLogger("voice-live-demo").info(
        "Agent rung disabled — set AGENT_ID and AGENT_PROJECT_NAME in .env to enable."
    )

_initial = _settings.mode if _settings.mode in _AVAILABLE else Mode.VOICELIVE
SHARED = SharedState(mode=_initial)

_initial_rung = REGISTRY[_initial]
handler = VoiceHandler(
    name=_initial_rung.mode.value,
    connect_factory=_initial_rung.connect_factory,
    make_session=_initial_rung.make_session,
    shared=SHARED,
)

demo = build_ui(
    rungs=[REGISTRY[m] for m in _AVAILABLE],
    initial_mode=_initial,
    settings=_settings,
    shared=SHARED,
    handler=handler,
    rtc_configuration=_rtc_configuration,
)

if __name__ == "__main__":
    from voicelive_demo.launcher import launch
    launch(demo, _settings)
