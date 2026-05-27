"""Rung 1 — Azure OpenAI Realtime.

This is the **before** in the demo's "before / after" story. It hits Azure
OpenAI's Realtime API directly via ``client.realtime.connect`` — the same
GA call shape ``openai 2.x`` exposes for the OpenAI cloud, just pointed at
a Foundry resource.

The diff against ``voicelive.py`` is **three small lines** (api-version,
``websocket_base_url``, ``extra_query``). The diff against ``agent.py``
swaps the ``extra_query`` dict for the agent triplet.
"""
from __future__ import annotations

from openai import AsyncAzureOpenAI

from voicelive_demo.config import azure_ad_token_provider, get_settings
from voicelive_demo.handler import SharedState
from voicelive_demo.i18n import REALTIME_VOICE_NAMES


def make_session(shared: SharedState) -> dict:
    """Session config sent on every (re)connection.

    The Realtime API accepts only the OpenAI voice set (alloy, ash, ballad,
    coral, echo, sage, shimmer, verse, marin, cedar). Anything else gets
    filtered down to ``alloy`` so a stale Voice Live voice selection can't
    blow up the connection during a rung switch — the UI also snaps the
    picker to a valid value, so this is belt-and-braces.
    """
    voice = shared.voice if shared.voice in REALTIME_VOICE_NAMES else "alloy"
    return {
        "turn_detection": {"type": "server_vad"},
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "voice": voice,
        "instructions": shared.instructions,
        "modalities": ["text", "audio"],
        "input_audio_transcription": {
            "model": "whisper-1",
            "language": shared.locale,
        },
    }


async def connect_factory():
    """The per-rung diff. Same SDK call shape for all three rungs."""
    settings = get_settings()
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint,
        api_version=settings.api_version_realtime,
        azure_ad_token_provider=azure_ad_token_provider,
    )
    return client.realtime.connect(
        model=settings.azure_deployment_name,
    )
