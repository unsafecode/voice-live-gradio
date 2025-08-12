import asyncio
import base64
import json
import logging
from pathlib import Path

import gradio as gr
import numpy as np
from openai import AsyncAzureOpenAI
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastrtc import (
    AdditionalOutputs,
    AsyncStreamHandler,
    Stream,
    get_twilio_turn_credentials,
    wait_for_item,
)
from gradio.utils import get_space
from config import config, azure_ad_token_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

cur_dir = Path(__file__).parent

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
            websocket_base_url=config.azure_voice_live_endpoint
        )
        async with self.client.beta.realtime.connect(
            model=config.azure_deployment_name,
            extra_query={
                "model": config.azure_deployment_name,  # need to redundantly specify model
            }
        ) as conn:
            logger.info("Connected to Azure realtime API.")
            await conn.session.update(
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
                if event.type == "conversation.item.input_audio_transcription.completed":
                    logger.info("Transcription completed: %s", event.transcript)
                    await self.output_queue.put(
                        AdditionalOutputs({"role": "user", "content": event.transcript})
                    )
                if event.type == "response.audio_transcript.done":
                    logger.info("Assistant response completed: %s", event.transcript)
                    await self.output_queue.put(
                        AdditionalOutputs({"role": "assistant", "content": event.transcript})
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
    rtc_configuration=get_twilio_turn_credentials() if get_space() else None,
    concurrency_limit=5 if get_space() else None,
    time_limit=90 if get_space() else None,
)

app = FastAPI()

stream.mount(app)


@app.get("/")
async def _():
    logger.info("Serving main HTML page.")
    rtc_config = get_twilio_turn_credentials() if get_space() else None
    html_content = (cur_dir / "index.html").read_text()
    html_content = html_content.replace("__RTC_CONFIGURATION__", json.dumps(rtc_config))
    return HTMLResponse(content=html_content)


@app.get("/outputs")
def _(webrtc_id: str):
    logger.info("Starting streaming response for outputs. webrtc_id: %s", webrtc_id)

    async def output_stream():
        import json

        async for output in stream.output_stream(webrtc_id):
            s = json.dumps(output.args[0])
            logger.debug("Streaming output: %s", s)
            yield f"event: output\ndata: {s}\n\n"

    return StreamingResponse(output_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    logger.info("Application starting in mode: %s", config.mode)
    if config.mode == "UI":
        logger.info("Launching UI server.")
        stream.ui.launch(server_port=7860, debug=False, show_error=True)
    elif config.mode == "PHONE":
        logger.info("Launching FastPhone server.")
        stream.fastphone(host="0.0.0.0", port=7860)
    else:
        logger.info("Running FastAPI server with uvicorn.")
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=7860)
