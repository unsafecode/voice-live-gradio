# Benchmark — scenario matrix × iterations, real numbers

A small harness that runs a **matrix of `mode:model` scenarios** through the
same fixed conversation, repeats each scenario `--iterations` times to absorb
pay-as-you-go noise, and writes per-turn metrics + WAV recordings for offline
review.

> ⚠️ For personal use / scientific spot-checks, not for customer-facing
> claims. The LLM is non-deterministic and Azure PAYG latency drifts —
> always look at p50 / p95 / CoV%, never a single sample.

## What it does

For each scenario in the matrix (default: 5 scenarios — one Realtime
baseline + four Voice Live flavours):

1. Opens a fresh `AsyncAzureOpenAI` connection (mode-appropriate URL +
   api-version + Entra ID token, no API keys).
2. Sends a fixed conversation script via **text input** (so we measure the
   same flow on every rung — STT / VAD are out of scope here).
3. Records every assistant audio response into a `.wav` file.
4. Captures per-turn metrics:
   - `ttfa_ms` — request → first audio chunk
   - `ttft_ms` — request → first text/transcript token
   - `total_response_ms` — request → `response.done`
   - `audio_duration_ms` — wall-clock duration of the generated audio
   - `audio_bytes` / `audio_chunks` / `transcript`
5. Repeats the whole scenario `--iterations` times (default 3) with a small
   inter-iteration delay.
6. Writes `metrics.json` + a human-readable `comparison.md` aggregating
   across (iterations × turns) — `min`, `p50`, `mean`, `p95`, `max`, and
   **CoV%** (coefficient of variation, a noise indicator).

## The default matrix

| Scenario | What it shows |
|----------|---------------|
| `realtime:gpt-realtime-1.5` | Rung 1 — your own deployment via the Azure OpenAI Realtime API |
| `voicelive:gpt-realtime` | Rung 2 — Voice Live's hosted realtime model (zero deployment) |
| `voicelive:gpt-realtime-mini` | Rung 2 — smaller hosted realtime model |
| `voicelive:gpt-5-mini` | Rung 2 — **text** model wrapped with Azure TTS by Voice Live |
| `voicelive:gpt-4o-mini` | Rung 2 — another text model wrapped with Azure TTS |

Voice Live publishes its own [allow-list of managed models](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live#supported-models-and-regions)
— you do **not** need to deploy them yourself. The list currently includes
`gpt-realtime`, `gpt-realtime-mini`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`,
`gpt-4.1-mini`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-chat`,
`phi4-mm-realtime`, and `phi4-mini`. Any of them work as `--scenarios
voicelive:<name>`.

## Quickstart

```bash
# default matrix, 3 iterations × 4 turns = 12 samples per scenario
uv run python -m benchmark.run

# bump iterations for tighter PAYG noise absorption
uv run python -m benchmark.run --iterations 5

# pick a specific subset
uv run python -m benchmark.run --scenarios voicelive:gpt-5-mini voicelive:gpt-4o-mini

# more turns per iteration
uv run python -m benchmark.run --turns 6 --iterations 5

# custom prompts (one per line)
uv run python -m benchmark.run --prompts my_prompts.txt --turns 6

# metrics only, no recordings
uv run python -m benchmark.run --no-wav

# explicit output directory (otherwise auto-timestamped under benchmark/results/)
uv run python -m benchmark.run --out /tmp/today
```

The `agent` rung is opt-in (`--scenarios agent:<model>`) because it needs
`AGENT_ID` + `AGENT_PROJECT_NAME` in `.env`.

## Output

```
benchmark/results/<timestamp>/
├── metrics.json                                  ← machine-readable, full payload
├── comparison.md                                 ← headline + full stats + per-iter drill-down
├── realtime-gpt-realtime-1.5_iter01_turn01.wav
├── realtime-gpt-realtime-1.5_iter01_turn02.wav
├── voicelive-gpt-realtime_iter01_turn01.wav
├── voicelive-gpt-5-mini_iter01_turn01.wav
└── …
```

Open `comparison.md` for the side-by-side tables; play the WAVs in any
audio player (24 kHz mono 16-bit PCM). Both the folder and its contents
are gitignored.

## Caveats

- **Text input** bypasses VAD / STT / echo cancellation — these numbers
  are a **lower bound** on real-world latency.
- The LLM is non-deterministic, so reply lengths (and therefore
  `total_response_ms` + `audio_duration_ms`) vary between runs. Bump
  `--iterations` and read `p50` / `p95` / `CoV%`, not single samples.
- **Voice Live + text models** include a TTS overlay, so audio duration
  tracks text length more loosely than a native realtime model — compare
  TTFA / TTFT for the closest apples-to-apples view.
- Network conditions matter. Run several times before drawing
  conclusions; ideally from the same machine + region.
- Voice Live's hosted-model menu evolves independently of your Foundry
  resource's deployments. Always cross-check the
  [official list](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live#supported-models-and-regions)
  if a new `--scenarios voicelive:<name>` fails with "Model … is not
  supported in this region."
