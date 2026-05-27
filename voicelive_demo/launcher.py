"""Shared `demo.launch(...)` wrapper so every entry point honours HOST/PORT.

All five shells (`app.py`, `app_demo.py`, `app_realtime.py`,
`app_voicelive.py`, `app_agent.py`) call this rather than calling
`demo.launch()` themselves, so the bind address + port stay in sync with
the rest of the env-configured settings.
"""
from __future__ import annotations

import logging
from typing import Any

from voicelive_demo.config import Settings

logger = logging.getLogger("voice-live-demo")


def launch(demo: Any, settings: Settings, **kwargs: Any) -> None:
    """Launch the Gradio app with HOST/PORT taken from settings."""
    logger.info("Listening on http://%s:%s", settings.host, settings.port)
    demo.launch(
        server_name=settings.host,
        server_port=settings.port,
        show_error=True,
        **kwargs,
    )
