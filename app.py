"""Dispatcher — picks the right app shell based on the MODE env var.

By default (``MODE`` unset or ``MODE=demo``) the unified switcher UI
launches, with all three rungs reachable from one page. The single-mode
shells stay supported for the pedagogical "look how minimal one rung is"
story:

    MODE=demo       → app_demo.py        (unified switcher — default)
    MODE=realtime   → app_realtime.py    (rung 1 only — Azure OpenAI Realtime)
    MODE=voicelive  → app_voicelive.py   (rung 2 only — Azure Voice Live)
    MODE=agent      → app_agent.py       (rung 3 only — Voice Live + Foundry Agent)

The four entry points share the same connection logic (in
``voicelive_demo/rungs/``) and the same UI (in ``voicelive_demo/ui.py``).
"""
from __future__ import annotations

import importlib
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("voice-live-demo")

MODE_TO_MODULE = {
    "demo":      "app_demo",
    "realtime":  "app_realtime",
    "voicelive": "app_voicelive",
    "agent":     "app_agent",
}


def main() -> None:
    mode = os.getenv("MODE", "demo").strip().lower()
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
