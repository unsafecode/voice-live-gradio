from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from azure.identity.aio import get_bearer_token_provider, DefaultAzureCredential


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='allow')

    azure_endpoint: str = Field(..., alias="AZURE_OPENAI_ENDPOINT")
    azure_api_version: str = Field(..., alias="AZURE_OPENAI_API_VERSION")
    azure_deployment_name: str = Field("gpt-4.1", alias="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_voice_live_endpoint: str = Field(..., alias="AZURE_VOICE_LIVE_ENDPOINT")
    mode: str = Field(..., alias="MODE")


azure_ad_token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",)

config = Settings()  # type: ignore

assert config.azure_endpoint, "AZURE_OPENAI_ENDPOINT must be set in .env file"