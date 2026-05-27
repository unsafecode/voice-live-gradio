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

## Voice Live ↔ Realtime — what's actually different

The single most common evaluation question is some variant of *"how is
Voice Live different from raw Realtime, and is the realtime model
behind it the same?"*. Short answer:

> **Voice Live is Azure OpenAI Realtime + server-side speech
> augmentations.** Same `gpt-realtime` model on both sides of the wire,
> same `openai` Python SDK, same `client.realtime.connect` call. The
> only on-wire difference is that Voice Live moves a handful of
> components from your app into the platform.

### Architecture — *not* a STT → LLM → TTS pipeline

Common misconception worth nailing down before any evaluation: Voice
Live is **not** "transcription → text to LLM → speech synthesis"
chained in series. The realtime model still does native
speech-to-speech (same `gpt-realtime`). The server-side components
(VAD, echo cancel, noise reduction, transcription) run **alongside**
the stream and produce *signals* the realtime model already knew how
to consume on the Realtime API — you just don't have to produce them
yourself anymore.

```
                Azure OpenAI Realtime                Azure Voice Live
                ─────────────────────                ────────────────
  ┌──────────┐                                                                ┌──────────┐
  │ Browser  │                                                                │ Browser  │
  └────┬─────┘                                                                └────┬─────┘
       │ WebRTC (FastRTC)                                                          │ WebRTC (FastRTC)
       │                                                                           │
  ┌────▼─────┐                                                                ┌────▼─────┐
  │ Your app │ ──── WS ───► [gpt-realtime]                                    │ Your app │ ──── WS ───► [VAD ┊ EC ┊ NR ┊ STT ┊ gpt-realtime ┊ HD TTS ┊ Agent routing]
  │  + VAD   │                                                                └──────────┘
  │  + EC/NR │
  │  + STT   │
  └──────────┘
```

The boundary moves rightward — that's the whole story. **Fluidity is
bound by the model, not the wrapper.** If Realtime feels fluid on a
given deployment, Voice Live on the same deployment feels identical.

### Who owns what

| Component | Realtime | Voice Live |
|---|---|---|
| Model (`gpt-realtime`, `gpt-realtime-mini`, …) | ✅ same | ✅ same |
| SDK call shape (`client.realtime.connect`) | ✅ same | ✅ same |
| VAD / turn detection | you (client-side `turn_detection`) | **platform** (optional semantic VAD, dedicated model) |
| Barge-in (user interrupts model) | you | **platform** |
| Echo cancel + noise reduction | you (or browser, lossy) | **platform** (Azure Speech stack) |
| Transcription (user-speech STT) | you (separate Whisper call) | **platform** (`azure-fast-transcription`, same WS) |
| TTS rendering | OpenAI voices only | OpenAI voices **+** Azure Neural HD multilingual |
| Agent routing (tool orchestration) | you | **platform** (with Foundry Agent — rung 3) |
| WebRTC pipe to browser | **you** | **you** |
| Audio queue + transcript fan-out | **you** | **you** |
| System instructions / persona | **you** | **you** (or the hosted agent owns it in rung 3) |

What stays with you is unchanged — that's why the three rungs in this
repo share `voicelive_demo/handler.py` byte-for-byte.

### FAQ — the seven questions every evaluator asks

**1. Is Voice Live a traditional STT→LLM→TTS pipeline, or really
native realtime?** Native realtime. The model is `gpt-realtime`
(speech-to-speech). The server-side STT exists for the user-input
transcript (so you can render it), not as a step in the model loop.

**2. Which components does the platform handle vs the application?**
See the "Who owns what" table above. Briefly: VAD / barge-in / EC / NR
/ STT / TTS rendering move server-side; WebRTC, audio queue, UI
transcript stay client-side.

**3. Which WebSocket events must my app handle to avoid latency
accumulation?** Three: (a) play `response.audio.delta` immediately —
don't buffer beyond the current chunk; (b) flush the playback queue on
`input_audio_buffer.speech_started` — that's the barge-in signal; (c)
send acks if the SDK doesn't (the `openai` 2.x SDK does). All three
already live in [`voicelive_demo/handler.py`](voicelive_demo/handler.py)
via FastRTC — read it, it's ~150 lines.

**4. Does Voice Live handle waiting for the user natively, or does my
app implement turn-taking?** Natively. `session.input_audio.turn_detection.type = "azure_semantic_vad"`
gives you a Whisper-class VAD on the platform side. You can also opt
out and run your own VAD client-side (set it to `null` / `"server_vad"`).

**5. Do I have to implement turn management, accumulation, response
resumption manually?** No. Voice Live keeps conversation state
server-side: turn history, audio accumulation, transcript. The
`conversation.item.*` and `response.*` events tell you what happened;
your only job is to render them.

**6. Does TTS start streaming as text generates, or only after the
full response?** Streaming. `response.audio.delta` events fire as the
model emits audio frames, well before `response.done`. The default in
this demo plays them straight through FastRTC with no extra buffering.

**7. Does Voice Live keep conversational sync internally, or must my
app maintain it?** Server-side. Reload the page → fresh
`client.realtime.connect()` resumes cleanly. Your app holds only the
UI copy of the transcript.

### Pricing

Voice Live has its own line item on the
[Azure AI Foundry pricing page](https://azure.microsoft.com/pricing/details/ai-foundry/)
distinct from raw Realtime. The server-side components (VAD, NR, STT,
HD TTS) are billed separately from the model token rate. For an honest
comparison vs raw Realtime: identical model price + add-on for the
augmentations you actually enable. Run [`benchmark/run.py`](benchmark/README.md)
for measured latency numbers under your own load.

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

## Models in play

| Deployment | Version | Used by | Notes |
|---|---|---|---|
| `gpt-realtime-1.5` | `2026-02-23` | **All three rungs (default)** | The newest model Voice Live serves in Sweden Central as of May 2026 — keeps the cross-rung diff symmetric. |
| `gpt-realtime-2` | `2026-05-06` | Optional override for rung 1 | The newest realtime model anywhere. Voice Live's hosted menu hasn't picked it up yet; will move all 3 rungs to it the day it lands. |

> Voice Live additionally hosts a curated allow-list of **managed** models
> you don't have to deploy yourself (`gpt-realtime`, `gpt-realtime-mini`,
> `gpt-5-mini`, `gpt-4o-mini`, …). The unified switcher and the
> benchmark reach these through the same `extra_query={"model": …}` knob —
> no Foundry-side change required.

## Getting started

### Prerequisites

- Python `>=3.13`
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and `ffmpeg` (for PyAV / FastRTC's WebRTC pipe)
- An Azure AI Foundry resource in a [Voice-Live-supported region](https://learn.microsoft.com/azure/ai-services/speech-service/regions?tabs=voice-live#regions)
  with `gpt-realtime-1.5` (or any realtime model the region serves) deployed
- An Entra ID identity with `Cognitive Services User` on the Foundry
  resource — **no API keys** anywhere
- (Optional, agent rung only) a Foundry Agent provisioned in the same project

### Quickstart

```bash
git clone https://github.com/unsafecode/voice-live-gradio
cd voice-live-gradio
cp .env.example .env       # edit endpoint + deployment, (optional) agent vars
uv sync
az login                   # ChainedTokenCredential reads this for local dev
uv run app.py              # serves http://localhost:7860
```

Open `http://localhost:7860` in a browser, grant mic permission, click the
mic to (re)connect, talk.

### Switching rungs

By default `uv run app.py` boots the **unified switcher** — all three
rungs reachable from one UI via a segmented control in the header. Click
a rung, click the mic to (re)connect, the next WebSocket lands at the
new destination. No restart.

```bash
uv run app.py                    # unified switcher (default — MODE=demo)
MODE=realtime   uv run app.py    # single-mode: Azure OpenAI Realtime
MODE=voicelive  uv run app.py    # single-mode: Azure Voice Live
MODE=agent      uv run app.py    # single-mode: Voice Live + Foundry Agent
```

Or run any single-mode shell directly: `uv run app_voicelive.py`. They
all share the same `connect_factory` / `make_session` callables — defined
once in `voicelive_demo/rungs/{realtime,voicelive,agent}.py` — so the
unified switcher and the **Switch diff** tab stay in lockstep with what
each shell actually runs.

The Agent rung is auto-disabled in the unified switcher if `AGENT_ID`
and `AGENT_PROJECT_NAME` aren't set in `.env`.

## What's new in the UI

- **Header chip** — at-a-glance MODE / MODEL / ENDPOINT.
- **Language switcher** — top-right of the hero. Swaps the interface
  (labels, buttons, status pill, blurbs, diff cards, About) **and** the
  voice + transcription language atomically. English + Italian ship in
  the box; add a third in ~10 lines (see [Localization](#localization)).
- **Live status** — Idle → Connecting → Listening 🎙️ → Thinking → Speaking 🔊 → Error.
- **Voice picker** — curated Azure Neural HD + OpenAI voices per locale;
  applies on next session.
- **System instructions** field — tweak persona without editing code.
- **Reset conversation** — clears the transcript.
- **Connection details panel** — endpoint, WSS URL, mode, auth method.
- **🧩 View the diff tab** — renders the two diffs above with `difflib.HtmlDiff`,
  computed from the live source files.
- **ℹ️ About tab** — what each rung does and where it sits on the GA
  timeline.

## Localization

The interface and the model's voice + transcription language are wired
together so visitors see (and hear) one consistent experience. All
strings, voice option lists, and per-locale system-prompt defaults live
in [`voicelive_demo/i18n.py`](voicelive_demo/i18n.py). Ships with:

- 🇬🇧 **English** — DragonHD voices (Ava, Andrew, Emma, Brian, Aria, Davis) + OpenAI Marin/Cedar.
- 🇮🇹 **Italian** — Multilingual Neural voices (Isabella, Giuseppe, Alessio) + standard Neural (Marta, Diego, Elsa) + OpenAI Nova/Shimmer.

Adding a new locale is one entry per dict in `i18n.py`
(`LOCALES`, `VOICE_OPTIONS`, `DEFAULT_VOICE`, `DEFAULT_INSTRUCTIONS`,
`STRINGS`, `STATUS_LABELS`, `RUNG_BLURBS`, plus a `diff_section1_*` /
`diff_section2_*` block in `STRINGS`). The pill switcher auto-renders
one button per `LOCALES` entry. The active locale is passed straight
into `session.input_audio_transcription.language` so the model
transcribes in the right language regardless of accent.

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

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Missing required environment variables` on launch | `.env` not copied or `AZURE_OPENAI_ENDPOINT` / `AZURE_VOICELIVE_ENDPOINT` blank | `cp .env.example .env` and fill the two endpoint URLs |
| `401` or `403` on first mic click | Your Entra identity lacks `Cognitive Services User` on the Foundry resource | Grant the role, then `az logout && az login` |
| WebRTC widget says "Click to Access Microphone" forever | Browser blocked mic permission | Open browser site settings, allow microphone for `localhost:7860`, refresh |
| Port 7860 already in use | A previous run is still bound | `lsof -tiTCP:7860 -sTCP:LISTEN` then `kill <pid>` |
| Agent rung greyed out in switcher | `AGENT_ID` / `AGENT_PROJECT_NAME` unset | Provision a Foundry Agent in your project, paste IDs into `.env`, restart |
| Voice quality dips when switching to Italian | Italian uses Multilingual Neural; English uses DragonHD (newer) | Expected; pick `Marta`/`Diego`/`Elsa` for standard Italian Neural which can sound crisper on short phrases |

