"""Rung 2 — Azure AI Foundry Voice Live · single-mode shell.

Standalone entry point that boots only the Voice Live rung. The actual
connection logic lives in :mod:`voicelive_demo.rungs.voicelive` so the
unified ``app.py`` switcher and the **Switch diff** tab share it.

Run with ``python app_voicelive.py`` (or ``MODE=voicelive python app.py``).
"""
from __future__ import annotations

import logging

from voicelive_demo.config import Mode, get_settings
from voicelive_demo.handler import SharedState, VoiceHandler
from voicelive_demo.rungs import REGISTRY
from voicelive_demo.ui import build_ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
_settings = get_settings()
_rung = REGISTRY[Mode.VOICELIVE]
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
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
