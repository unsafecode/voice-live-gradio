# Voice Live Gradio Demo — May 2026 GA Refresh

> **How trivial is it to switch from Azure OpenAI Realtime to Azure AI Foundry
> Voice Live?** Three lines, same SDK. This repo proves it — three sibling
> apps that share **all** their plumbing and differ **only** in the
> connection-setup block.

![Audio chatbot UI with status badges, voice picker, and a "View the diff" tab.](image.png)

## What's in the box

```
voice-live-gradio/
├── app_realtime.py        ← rung 1: Azure OpenAI Realtime  (the "before")
│      │
│      ▼   diff = 3 small lines (api-version, websocket_base_url, extra_query)
├── app_voicelive.py       ← rung 2: Azure Voice Live       (the punchline)
│      │
│      ▼   diff = 1 line (extra_query gains agent-id / -project-name / -access-token)
├── app_agent.py           ← rung 3: Voice Live + Foundry Agent
├── app.py                 ← thin dispatcher (reads MODE env var)
└── voicelive_demo/        ← all shared plumbing — UI, handler, diff renderer
```

Open the running UI and click **🧩 View the diff** for a side-by-side render
of the two diffs above. The "trivial switch" is literally on screen.

## The diff, condensed

```python
# rung 1 — Azure OpenAI Realtime
client = AsyncAzureOpenAI(
    azure_endpoint=settings.azure_endpoint,
    api_version="2025-04-01-preview",                       # ← preview today
    azure_ad_token_provider=azure_ad_token_provider,
)
return client.realtime.connect(model=settings.azure_deployment_name)

# rung 2 — Azure AI Foundry Voice Live  (3 added/changed lines)
client = AsyncAzureOpenAI(
    azure_endpoint=settings.azure_endpoint,
    api_version="2025-10-01",                               # ← GA
    azure_ad_token_provider=azure_ad_token_provider,
    websocket_base_url=settings.azure_voice_live_endpoint,  # ← /voice-live
)
return client.realtime.connect(
    model=settings.azure_deployment_name,
    extra_query={"model": settings.azure_deployment_name},  # ← &model= not &deployment=
)

# rung 3 — Voice Live + Foundry Agent  (extra_query gets 3 routing keys)
return client.realtime.connect(
    model=settings.azure_deployment_name,
    extra_query={
        "agent-id":           settings.agent_id,
        "agent-project-name": settings.agent_project_name,
        "agent-access-token": await azure_agent_token_provider(),
    },
)
```

Everything else — the FastRTC mic pipe, the Gradio Blocks UI, the status
badges, the voice picker, the transcript fan-out — lives in
`voicelive_demo/` and is **identical across all three rungs**.

## Why are there 3 lines, not 1?

The original demo claimed "one line — just `websocket_base_url`". As of May
2026 that's *almost* still true:

1. **`websocket_base_url`** — yes, still the headline change.
2. **`api_version` differs** between rungs because Realtime is still on
   `2025-04-01-preview` (the `openai 2.x` SDK keeps emitting
   `/openai/realtime` — when it adopts the GA `/openai/v1/realtime` URL we
   can collapse this difference). Voice Live is **GA** on `2025-10-01`.
3. **`extra_query={"model": ...}`** — the SDK adds `&deployment=…` to the
   WSS URL; Voice Live keys off `&model=…`, so we add it explicitly. Tiny.

## Models in play (Foundry resource: `emea-aigbb-demos-oai`, Sweden Central)

| Deployment | Version | Used by | Notes |
|---|---|---|---|
| `gpt-realtime-1.5` | `2026-02-23` | **All three rungs (default)** | The newest model Voice Live serves in Sweden Central as of May 2026 — keeps the cross-rung diff symmetric. |
| `gpt-realtime-2` | `2026-05-06` | Optional override for rung 1 | The newest realtime model anywhere. Voice Live's hosted menu hasn't picked it up yet; will move all 3 rungs to it the day it lands. |

## Getting started

### Prerequisites

- Python `>=3.13`
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and `ffmpeg` (for PyAV / FastRTC's WebRTC pipe)
- An Azure AI Foundry resource with `gpt-realtime-1.5` (or any realtime
  model your region serves) deployed
- An Entra ID identity with `Cognitive Services User` on the Foundry
  resource — **no API keys** anywhere

### Quickstart

```bash
git clone https://github.com/Azure-Samples/voice-live-gradio
cd voice-live-gradio
cp .env.example .env       # edit endpoint, deployment, (optional) agent vars
uv sync
az login                   # ChainedTokenCredential reads this for local dev
uv run app.py              # serves http://localhost:7860
```

### Switching rungs

```bash
MODE=realtime   uv run app.py   # Azure OpenAI Realtime
MODE=voicelive  uv run app.py   # Azure Voice Live      ← default
MODE=agent      uv run app.py   # Voice Live + Foundry Agent
```

Or run any rung directly: `uv run app_voicelive.py`. They each expose a
top-level `demo` Gradio Blocks; `app.py` is just a one-of-three importer.

## What's new in the UI

- **Header chip** — at-a-glance MODE / MODEL / ENDPOINT.
- **Live status** — Idle → Connecting → Listening 🎙️ → Thinking → Speaking 🔊 → Error.
- **Voice picker** — curated Azure Neural HD + OpenAI voices; applies on
  next session.
- **System instructions** field — tweak persona without editing code.
- **Reset conversation** — clears the transcript.
- **Connection details panel** — endpoint, WSS URL, mode, auth method.
- **🧩 View the diff tab** — renders the two diffs above with `difflib.HtmlDiff`,
  computed from the live source files.
- **ℹ️ About tab** — what each rung does and where it sits on the GA
  timeline.

## Auth

Everything is **Entra ID** via `azure.identity.aio.DefaultAzureCredential`:

- Realtime + Voice Live model scope: `https://cognitiveservices.azure.com/.default`
- Foundry Agent scope: `https://ai.azure.com/.default`

No API keys are present in `.env.example` or anywhere in the source.

## Benchmark

Want real numbers? `benchmark/run.py` runs a **scenario matrix**
(mode × model) × `--iterations` × `--turns` over the *exact same*
conversation and emits a markdown report with p50 / p95 / CoV% plus
per-turn WAVs. The default matrix exercises the Realtime baseline
**and** Voice Live's hosted realtime *and* text-model flavours so you
can see the TTS-overlay tax in one chart.

```bash
uv run python -m benchmark.run                       # default 5-scenario matrix, 3 iter × 4 turns
uv run python -m benchmark.run --iterations 5        # tighter PAYG noise absorption
uv run python -m benchmark.run --scenarios voicelive:gpt-5-mini voicelive:gpt-4o-mini
```

See [`benchmark/README.md`](benchmark/README.md) for the full matrix
syntax, output layout, and caveats.

## Resources

- [Voice Live overview](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
- [Voice Live quickstart (Foundry models)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-quickstart?tabs=windows%2Ckeyless&pivots=programming-language-python)
- [Voice Live quickstart (Foundry Agents)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-agents-quickstart?tabs=windows%2Ckeyless&pivots=programming-language-python)
- [Regional availability](https://learn.microsoft.com/azure/ai-services/speech-service/regions?tabs=voice-live#regions)
- [Original FastRTC adapter sample](https://huggingface.co/spaces/fastrtc/talk-to-openai/blob/main/app.py)

