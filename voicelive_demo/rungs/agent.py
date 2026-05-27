"""Rung 3 — Azure AI Foundry Voice Live + Foundry Agent.

The same Voice Live entrypoint as ``voicelive.py``, with the
``extra_query`` dict extended to route the WebSocket to a hosted
Foundry Agent instead of a raw model. The agent owns the instructions
and any tools, so ``make_session`` is leaner.
"""
from __future__ import annotations

from openai import AsyncAzureOpenAI

from voicelive_demo.config import (
    azure_ad_token_provider,
    azure_agent_token_provider,
    get_settings,
)
from voicelive_demo.handler import SharedState


def make_session(shared: SharedState) -> dict:
    """Session config sent on every (re)connection."""
    return {
        "turn_detection": {"type": "azure_semantic_vad", "remove_filler_words": False},
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "voice": {"name": shared.voice, "type": shared.voice_type},
        "modalities": ["text", "audio"],
        "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
        "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
        "input_audio_transcription": {
            "model": "azure-fast-transcription",
            "language": shared.locale,
        },
    }


async def connect_factory():
    """The per-rung diff. Same SDK call shape for all three rungs."""
    settings = get_settings()
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
