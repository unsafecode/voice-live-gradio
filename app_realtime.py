"""Rung 1 — Azure OpenAI Realtime · single-mode shell.

Standalone entry point that boots only the Realtime rung. The actual
connection logic lives in :mod:`voicelive_demo.rungs.realtime` so the
unified ``app.py`` switcher and the **Switch diff** tab share it.

Run with ``python app_realtime.py`` (or ``MODE=realtime python app.py``).
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
_rung = REGISTRY[Mode.REALTIME]
SHARED = SharedState(mode=_rung.mode)

handler = VoiceHandler(
    name=_rung.mode.value,
    connect_factory=_rung.connect_factory,
    make_session=_rung.make_session,
    shared=SHARED,
)

demo = build_ui(
    rungs=[_rung],
    initial_mode=_rung.mode,
    settings=_settings,
    shared=SHARED,
    handler=handler,
    rtc_configuration=_rtc_configuration,
)

if __name__ == "__main__":
    from voicelive_demo.launcher import launch
    launch(demo, _settings)
