"""Voice Live demo — shared plumbing for the three demo apps.

This package exists so the three `app_*.py` files at the repo root can stay
*structurally identical* except for the connection-setup block. That block
*is* the punchline of the demo: it's how trivial it is to switch from Azure
OpenAI Realtime to Azure AI Foundry Voice Live (or to a Foundry Agent).
"""
from voicelive_demo.config import Mode, Settings, get_settings
from voicelive_demo.handler import SharedState, StatusEvent, VoiceHandler
from voicelive_demo.ui import build_ui

__all__ = [
    "Mode",
    "Settings",
    "SharedState",
    "StatusEvent",
    "VoiceHandler",
    "build_ui",
    "get_settings",
]
