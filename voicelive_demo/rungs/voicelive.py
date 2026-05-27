"""Rung 2 — Azure AI Foundry Voice Live.

This is the **after**. Same SDK, same call shape, same Foundry resource as
``realtime.py`` — only the connection block differs:

  * ``api_version`` is the GA Voice Live one (``2025-10-01``);
  * ``websocket_base_url`` redirects WebSocket traffic to the
    ``/voice-live`` endpoint on ``services.ai.azure.com``;
  * ``extra_query={"model": ...}`` because Voice Live keys off
    ``&model=`` not the ``&deployment=`` the SDK adds by default.

Everything else — UI, handler, transcript fan-out — is shared.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from openai import AsyncAzureOpenAI

from voicelive_demo.config import azure_ad_token_provider, get_settings
from voicelive_demo.handler import SharedState


def make_session(shared: SharedState) -> dict:
    """Session config sent on every (re)connection."""
    return {
        "turn_detection": {"type": "azure_semantic_vad", "remove_filler_words": False},
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "voice": {"name": shared.voice, "type": shared.voice_type},
        "instructions": shared.instructions,
        "modalities": ["text", "audio"],
        "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
        "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
        "input_audio_transcription": {
            "model": "azure-fast-transcription",
            "language": shared.locale,
        },
    }


@asynccontextmanager
async def connect_factory(*, model: str | None = None):
    """The per-rung diff. Same SDK call shape for all three rungs."""
    settings = get_settings()
    actual_model = model or settings.azure_deployment_name
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint,
        api_version=settings.api_version_voicelive,
        azure_ad_token_provider=azure_ad_token_provider,
        websocket_base_url=settings.azure_voice_live_endpoint,
    )
    try:
        async with client.realtime.connect(
            model=actual_model,
            extra_query={"model": actual_model},
        ) as conn:
            yield conn
    finally:
        await client.close()
