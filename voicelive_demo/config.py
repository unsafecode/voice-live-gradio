"""Settings for the three demo modes.

Each mode validates its own required fields lazily — `get_settings()` raises
with a friendly message if the env vars for that mode are missing.

Every knob is environment-configurable. Defaults target Azure Public Cloud;
override `AZURE_COGNITIVE_SERVICES_SCOPE` / `AZURE_AI_SCOPE` for sovereign
clouds (Gov, China, Germany). Override `HOST` / `PORT` to move the Gradio
server off the defaults (`0.0.0.0:7860`).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(str, Enum):
    REALTIME = "realtime"
    VOICELIVE = "voicelive"
    AGENT = "agent"
    DEMO = "demo"


class Settings(BaseSettings):
    """Environment-backed settings for all three demo modes.

    Required fields per mode are validated on `get_settings()`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False,
    )

    mode: Mode = Field(Mode.DEMO, alias="MODE")

    azure_endpoint: str = Field(
        ...,
        alias="AZURE_OPENAI_ENDPOINT",
        description="https://<your-foundry-resource>.openai.azure.com",
    )
    azure_deployment_name: str = Field(
        "gpt-realtime-1.5",
        alias="AZURE_OPENAI_DEPLOYMENT_NAME",
        description=(
            "Name of your realtime model deployment in the Foundry resource. "
            "Used by the Realtime rung (rung 1) — must be a `gpt-realtime-*` "
            "SKU because the Azure OpenAI Realtime endpoint does not accept "
            "cascade models like gpt-5."
        ),
    )

    azure_voice_live_endpoint: str = Field(
        ...,
        alias="AZURE_VOICELIVE_ENDPOINT",
        description="wss://<your-foundry-resource>.services.ai.azure.com/voice-live",
    )
    azure_voice_live_model: str = Field(
        "gpt-5",
        alias="AZURE_VOICE_LIVE_MODEL",
        description=(
            "Default model the Voice Live rung (rung 2) requests via "
            "`?model=<name>` on the Voice Live WS URL. Voice Live hosts a "
            "managed allow-list (gpt-5, gpt-5.4, gpt-5-mini, gpt-realtime-1.5, "
            "…) — no Foundry deployment of your own is needed for anything "
            "in that catalog. Default `gpt-5` matches the cascade model the "
            "customer's production stack uses for the same scenario; swap "
            "to `gpt-realtime-1.5` for lowest-latency native audio."
        ),
    )

    agent_project_name: Optional[str] = Field(None, alias="AGENT_PROJECT_NAME")
    agent_id: Optional[str] = Field(None, alias="AGENT_ID")
    agent_model: str = Field(
        "gpt-4.1-mini",
        alias="AGENT_MODEL",
        description=(
            "Chat-completion model deployment that backs the Foundry Prompt "
            "Agent used by rung 3. Separate from the realtime model in "
            "AZURE_OPENAI_DEPLOYMENT_NAME — Voice Live wraps STT/TTS around "
            "this reasoning model. Used only by the provisioner script."
        ),
    )

    api_version_realtime: str = Field("2025-04-01-preview", alias="AZURE_OPENAI_API_VERSION")
    api_version_voicelive: str = Field("2025-10-01", alias="AZURE_VOICELIVE_API_VERSION")

    cognitive_services_scope: str = Field(
        "https://cognitiveservices.azure.com/.default",
        alias="AZURE_COGNITIVE_SERVICES_SCOPE",
        description="Token scope for the realtime / Voice Live model. Override for sovereign clouds.",
    )
    ai_scope: str = Field(
        "https://ai.azure.com/.default",
        alias="AZURE_AI_SCOPE",
        description="Token scope for the Foundry Agent rung. Override for sovereign clouds.",
    )

    host: str = Field(
        "0.0.0.0",
        alias="HOST",
        description="Bind address for the Gradio server. Use 127.0.0.1 for loopback-only.",
    )
    port: int = Field(
        7860,
        alias="PORT",
        description="TCP port for the Gradio server.",
    )

    def validate_mode(self) -> None:
        if self.mode is Mode.AGENT and (not self.agent_id or not self.agent_project_name):
            raise RuntimeError(
                "MODE=agent requires both AGENT_ID and AGENT_PROJECT_NAME to be set in .env."
            )


def get_settings() -> Settings:
    try:
        s = Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise RuntimeError(
            "Missing required environment variables. Copy .env.example to .env "
            "and set AZURE_OPENAI_ENDPOINT and AZURE_VOICELIVE_ENDPOINT to point at "
            "your Azure AI Foundry resource. See README.md → Getting started."
        ) from exc
    s.validate_mode()
    return s


_credential = DefaultAzureCredential()


def _build_token_providers(settings: Settings) -> tuple:
    return (
        get_bearer_token_provider(_credential, settings.cognitive_services_scope),
        get_bearer_token_provider(_credential, settings.ai_scope),
    )


_settings_for_providers = get_settings()
azure_ad_token_provider, azure_agent_token_provider = _build_token_providers(
    _settings_for_providers
)


async def close_credential() -> None:
    """Close the module-level DefaultAzureCredential.

    Call this from CLI tools (e.g. the benchmark) so the underlying aiohttp
    session in azure-identity doesn't log "Unclosed client session" warnings
    when the event loop tears down.

    The Gradio app keeps the credential alive for the process lifetime, so
    no teardown is needed there.
    """
    try:
        await _credential.close()
    except Exception:
        pass
