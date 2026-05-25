"""Dispatcher — picks the right app_*.py based on the MODE env var.

This lets people keep doing `uv run app.py` (or `python app.py`) like before,
while the real entrypoint lives in one of the three rung-specific files.

    MODE=realtime   → app_realtime.py    (Azure OpenAI Realtime — rung 1)
    MODE=voicelive  → app_voicelive.py   (Azure Voice Live      — rung 2, default)
    MODE=agent      → app_agent.py       (Voice Live + Foundry Agent — rung 3)

The three apps are deliberately structurally identical except for the
connection-setup block. See the "View the diff" tab in the running UI.
"""
from __future__ import annotations

import importlib
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("voice-live-demo")

MODE_TO_MODULE = {
    "realtime":  "app_realtime",
    "voicelive": "app_voicelive",
    "agent":     "app_agent",
}


def main() -> None:
    mode = os.getenv("MODE", "voicelive").strip().lower()
    module_name = MODE_TO_MODULE.get(mode)
    if not module_name:
        logger.error(
            "Unknown MODE=%r. Pick one of: %s",
            mode, ", ".join(MODE_TO_MODULE.keys()),
        )
        sys.exit(2)

    logger.info("MODE=%s → launching %s", mode, module_name)
    module = importlib.import_module(module_name)
    demo = getattr(module, "demo")
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True)


if __name__ == "__main__":
    main()
