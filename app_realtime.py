"""Rung 1 — Azure OpenAI Realtime.

This is the **before** in the demo's "before / after" story. It hits Azure
OpenAI's Realtime API directly via ``client.realtime.connect`` — the same
GA call shape ``openai 2.x`` exposes for the OpenAI cloud, just pointed at
a Foundry resource.

Diff against ``app_voicelive.py`` is **three small lines** (api-version,
``websocket_base_url``, ``extra_query``). Diff against ``app_agent.py``
adds a fourth line in ``extra_query``.
"""
from __future__ import annotations

import logging
from openai import AsyncAzureOpenAI

from voicelive_demo.config import Mode, azure_ad_token_provider, get_settings
from voicelive_demo.handler import SharedState, VoiceHandler
from voicelive_demo.ui import build_ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
settings = get_settings()
MODE = Mode.REALTIME
SHARED = SharedState()


def make_session(shared: SharedState) -> dict:
    """Session config sent on every (re)connection."""
    return {
        "turn_detection": {"type": "server_vad"},
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "voice": "alloy",  # Realtime API supports the openai voice set only
        "instructions": shared.instructions,
        "modalities": ["text", "audio"],
        "input_audio_transcription": {"model": "whisper-1"},
    }


async def connect_factory():
    """The per-rung diff. Same SDK call shape for all three rungs."""
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint,
        api_version=settings.api_version_realtime,
        azure_ad_token_provider=azure_ad_token_provider,
    )
    return client.realtime.connect(model=settings.azure_deployment_name)


handler = VoiceHandler(
    name="realtime",
    connect_factory=connect_factory,
    make_session=make_session,
    shared=SHARED,
)

demo = build_ui(
    mode=MODE,
    model=settings.azure_deployment_name,
    endpoint=settings.azure_endpoint,
    voice_live_endpoint=settings.azure_voice_live_endpoint,
    shared=SHARED,
    handler=handler,
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
