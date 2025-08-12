# Voice Live API Gradio demo

This project demonstrates the integration of the Voice Live API with Gradio, enabling real-time voice interaction capabilities as drop-in
replacement over RealTime models.

Adapter from [https://huggingface.co/spaces/fastrtc/talk-to-openai/blob/main/app.py](https://huggingface.co/spaces/fastrtc/talk-to-openai/blob/main/app.py)

![Basic chatbot in audio-only mode showing a sample conversation about developer jokes](image.png)

## Features

- Straightforward UI thanks to Gradio
- Real-time voice interaction via Azure AI Foundry Voice Live API
- Drop-in replacement over OpenAI RealTime models
- Supports both connecting to AI Foundry models and AI Foundry Agents

## Getting Started

### Prerequisites

- Python >= 3.12
- `uv` package must be [installed](https://docs.astral.sh/uv/getting-started/installation/)

### Quickstart

1. `git clone https://github.com/Azure-Samples/voice-live-gradio`
2. `cd voice-live-gradio`
3. `cp .env.example .env`
4. Fill in `.env` with your Azure AI Foundry settings
5. `uv sync`
6. `uv run app.py`
7. Navigate to `http://localhost:7860`

## Resources

- [Original FastRTC sample](https://huggingface.co/spaces/fastrtc/talk-to-openai/blob/main/app.py)
- [Voice Live Overview](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live)
- [Connect to Foundry models](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-quickstart?tabs=windows%2Ckeyless&pivots=programming-language-python)
- [Connect to Foundry Agents](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-agents-quickstart?tabs=windows%2Ckeyless&pivots=programming-language-python)
- [Regional availability](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions?tabs=voice-live#regions)
