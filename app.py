import asyncio
import base64
import logging

import gradio as gr
import numpy as np
from openai import AsyncAzureOpenAI
from fastrtc import (
    AdditionalOutputs,
    AsyncStreamHandler,
    Stream,
    wait_for_item,
)
from config import config, azure_ad_token_provider, azure_agent_token_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000


class AzureVoiceLiveHandler(AsyncStreamHandler):
    def __init__(self) -> None:
        super().__init__(
            expected_layout="mono",
            output_sample_rate=SAMPLE_RATE,
            input_sample_rate=SAMPLE_RATE,
        )
        self.connection = None
        self.output_queue = asyncio.Queue()
        logger.info("AzureVoiceLiveHandler initialized.")

    def copy(self):
        logger.info("Copying AzureVoiceLiveHandler instance.")
        return AzureVoiceLiveHandler()

    async def start_up(self):
        """Connect to realtime API. Run forever in separate thread to keep connection open."""
        logger.info("Starting up and connecting to Azure realtime API.")
        self.client = AsyncAzureOpenAI(
            azure_endpoint=config.azure_endpoint,
            api_version=config.azure_api_version,
            azure_ad_token_provider=azure_ad_token_provider,
            websocket_base_url=config.azure_voice_live_endpoint,  # NOTE: This is slightly different than standard endpoint
        )

        # When targeting Foundry Agents params differ
        if config.agent_id and config.agent_project_name:
            agent_token = await azure_agent_token_provider()
            extra_query = {
                "agent-id": config.agent_id,
                "agent-project-name": config.agent_project_name,
                "agent-access-token": agent_token,
            }
        else:
            # Basic model target
            # Just need to redundantly specify model to map a different querystring key
            extra_query = {
                "model": config.azure_deployment_name,
            }

        # NOTE: this standard RealTime API connection
        async with self.client.beta.realtime.connect(
            model=config.azure_deployment_name,
            extra_query=extra_query,
        ) as conn:
            logger.info("Connected to Azure realtime API.")
            await conn.session.update(
                # NOTE: apply session settings as needed
                session={
                    "turn_detection": {
                        "type": "azure_semantic_vad",
                        "threshold": 0.3,
                        "prefix_padding_ms": 200,
                        "silence_duration_ms": 200,
                        "remove_filler_words": False,
                        "end_of_utterance_detection": {
                            "model": "semantic_detection_v1",
                            "threshold": 0.01,
                            "timeout": 2,
                        },
                    },
                    "input_audio_noise_reduction": {
                        "type": "azure_deep_noise_suppression"
                    },
                    "input_audio_echo_cancellation": {
                        "type": "server_echo_cancellation"
                    },
                    "voice": {
                        "name": "en-US-Ava:DragonHDLatestNeural",
                        "type": "azure-standard",
                        "temperature": 0.8,
                    },
                }  # type: ignore
            )
            self.connection = conn
            logger.info("Session updated. Listening for events...")
            async for event in self.connection:
                logger.debug("Received event: %s", event)
                # Handle interruptions
                if event.type == "input_audio_buffer.speech_started":
                    logger.info("Speech started. Clearing output queue.")
                    self.clear_queue()
                if (
                    event.type
                    == "conversation.item.input_audio_transcription.completed"
                ):
                    logger.info("Transcription completed: %s", event.transcript)
                    await self.output_queue.put(
                        AdditionalOutputs({"role": "user", "content": event.transcript})
                    )
                if event.type == "response.audio_transcript.done":
                    logger.info("Assistant response completed: %s", event.transcript)
                    await self.output_queue.put(
                        AdditionalOutputs(
                            {"role": "assistant", "content": event.transcript}
                        )
                    )
                if event.type == "response.audio.delta":
                    logger.debug("Received audio delta event.")
                    await self.output_queue.put(
                        (
                            self.output_sample_rate,
                            np.frombuffer(
                                base64.b64decode(event.delta), dtype=np.int16
                            ).reshape(1, -1),
                        )
                    )

    async def receive(self, frame: tuple[int, np.ndarray]) -> None:
        if not self.connection:
            logger.warning("No active connection. Dropping frame.")
            return
        _, array = frame
        array = array.squeeze()
        audio_message = base64.b64encode(array.tobytes()).decode("utf-8")
        logger.debug("Sending audio message to connection.")
        await self.connection.input_audio_buffer.append(audio=audio_message)  # type: ignore

    async def emit(self) -> tuple[int, np.ndarray] | AdditionalOutputs | None:
        output = await wait_for_item(self.output_queue)
        logger.debug("Emitting output: %s", output)
        return output

    async def shutdown(self) -> None:
        if self.connection:
            logger.info("Shutting down connection.")
            await self.connection.close()
            self.connection = None
        else:
            logger.info("No active connection to shutdown.")


def update_chatbot(chatbot: list[dict], response: dict):
    logger.info("Updating chatbot with new response: %s", response)
    chatbot.append(response)
    return chatbot


chatbot = gr.Chatbot(type="messages")
latest_message = gr.Textbox(type="text", visible=False)
stream = Stream(
    AzureVoiceLiveHandler(),
    mode="send-receive",
    modality="audio",
    additional_inputs=[chatbot],
    additional_outputs=[chatbot],
    additional_outputs_handler=update_chatbot,
)

if __name__ == "__main__":
    logger.info("Application starting in mode: %s", config.mode)
    stream.ui.launch(server_port=7860, debug=False, show_error=True)
