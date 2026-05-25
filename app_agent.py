"""Rung 3 — Azure AI Foundry Voice Live + Foundry Agent.

The same Voice Live entrypoint as ``app_voicelive.py``, with the
``extra_query`` dict extended to route the WebSocket to a hosted
Foundry Agent instead of a raw model. The agent owns the instructions
and any tools, so ``make_session`` is leaner.
"""
from __future__ import annotations

import logging
from openai import AsyncAzureOpenAI

from voicelive_demo.config import (
    Mode,
    azure_ad_token_provider,
    azure_agent_token_provider,
    get_settings,
)
from voicelive_demo.handler import SharedState, VoiceHandler
from voicelive_demo.ui import build_ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
settings = get_settings()
MODE = Mode.AGENT
SHARED = SharedState()


def make_session(shared: SharedState) -> dict:
    """Session config sent on every (re)connection. Agent owns instructions."""
    return {
        "turn_detection": {"type": "azure_semantic_vad", "remove_filler_words": False},
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "voice": {"name": shared.voice, "type": shared.voice_type},
        "modalities": ["text", "audio"],
        "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
        "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
        "input_audio_transcription": {"model": "azure-fast-transcription"},
    }


async def connect_factory():
    """The per-rung diff. Same SDK call shape for all three rungs."""
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint,
        api_version=settings.api_version_voicelive,
        azure_ad_token_provider=azure_ad_token_provider,
        websocket_base_url=settings.azure_voice_live_endpoint,
    )
    return client.realtime.connect(
        model=settings.azure_deployment_name,
        extra_query={
            "agent-id":           settings.agent_id,
            "agent-project-name": settings.agent_project_name,
            "agent-access-token": await azure_agent_token_provider(),
        },
    )


handler = VoiceHandler(
    name="agent",
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
