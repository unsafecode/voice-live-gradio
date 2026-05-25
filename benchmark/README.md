# Benchmark — same conversation, multiple rungs, real numbers

A tiny harness that hits each rung with the *exact* same conversation and
captures per-turn metrics + WAV recordings for offline review.

> ⚠️ For personal use / scientific spot-checks, not for customer-facing
> claims. Sample sizes here are small and the LLM is non-deterministic.

## What it does

For every rung you ask for (default: `realtime` + `voicelive`):

1. Spins up the same connection the demo uses (reuses each app's
   `connect_factory` + `make_session`).
2. Plays a fixed conversation script via **text input** (so we measure
   the same flow on both sides — STT / VAD are out of scope here).
3. Records every assistant audio response into a WAV file.
4. Captures per-turn metrics:
   - `ttfa_ms` — request → first audio chunk
   - `ttft_ms` — request → first text/transcript token
   - `total_response_ms` — request → `response.done`
   - `audio_duration_ms` — wall-clock duration of the generated audio
   - `audio_bytes` / `audio_chunks`
   - `transcript`
5. Writes `metrics.json` + a human-readable `comparison.md` with stats
   summary (min / p50 / mean / max).

## Quickstart

```bash
# all defaults (realtime + voicelive, 4 turns each)
uv run python -m benchmark.run

# one mode, more turns
uv run python -m benchmark.run --modes voicelive --turns 10

# custom prompts (one per line)
uv run python -m benchmark.run --prompts my_prompts.txt --turns 6

# pick the output directory
uv run python -m benchmark.run --out /tmp/today
```

The `agent` rung is opt-in (`--modes agent`) because it needs
`AGENT_ID` + `AGENT_PROJECT_NAME` in `.env`.

## Output

```
benchmark/results/<timestamp>/
├── metrics.json          ← machine-readable, full payload
├── comparison.md         ← human-readable summary + stats
├── realtime_turn_01.wav
├── realtime_turn_02.wav
├── voicelive_turn_01.wav
└── …
```

Open `comparison.md` for the side-by-side table; play the WAVs in any
audio player (24 kHz mono 16-bit PCM). Both folders and contents are
gitignored.

## Caveats

- **Text input** bypasses VAD / STT / echo cancellation — these
  numbers are a **lower bound** on real-world latency.
- The LLM is non-deterministic, so reply lengths (and therefore
  `total_response_ms` + `audio_duration_ms`) vary between runs. Use
  `--turns N` for more samples and compare `p50` / `mean`.
- Network conditions matter. Run several times before drawing
  conclusions; ideally from the same machine + region.
- Voice Live's hosted model menu is independent of Foundry deployments,
  so the comparison sticks to `gpt-realtime-1.5` (the newest Voice Live
  currently serves in Sweden Central).
