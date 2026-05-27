"""Settings for the three demo modes.

Each mode validates its own required fields lazily — `get_settings(mode)` raises
with a friendly message if the env vars for that mode are missing.
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

    Required fields per mode are validated on `get_settings(mode)`.
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
        description="Name of your realtime model deployment in the Foundry resource",
    )

    azure_voice_live_endpoint: str = Field(
        ...,
        alias="AZURE_VOICELIVE_ENDPOINT",
        description="wss://<your-foundry-resource>.services.ai.azure.com/voice-live",
    )

    agent_project_name: Optional[str] = Field(None, alias="AGENT_PROJECT_NAME")
    agent_id: Optional[str] = Field(None, alias="AGENT_ID")

    api_version_realtime: str = Field("2025-04-01-preview", alias="AZURE_OPENAI_API_VERSION")
    api_version_voicelive: str = Field("2025-10-01", alias="AZURE_VOICELIVE_API_VERSION")

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
azure_ad_token_provider = get_bearer_token_provider(
    _credential,
    "https://cognitiveservices.azure.com/.default",
)
azure_agent_token_provider = get_bearer_token_provider(
    _credential,
    "https://ai.azure.com/.default",
)
