"""Entrypoint for the FastAPI + WebSocket shell.

Run locally:

    MODE=voicelive uv run python app_web.py

Or, in the deployed container, the Dockerfile invokes::

    uvicorn app_web:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import logging
import os

from voicelive_demo.config import get_settings
from voicelive_demo.web_server import create_app

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(message)s",
)

app = create_app()

if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "app_web:app",
        host=s.host,
        port=s.port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
