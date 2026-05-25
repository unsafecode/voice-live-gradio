"""Benchmark runner — scenario matrix × iterations, with recordings + stats.

A "scenario" is a `mode:model` pair. Voice Live exposes a curated allow-list
of *managed* models — both native realtime (`gpt-realtime`, `gpt-realtime-mini`)
**and** text models wrapped with Azure Speech STT+TTS (`gpt-5`, `gpt-5-mini`,
`gpt-4o`, `gpt-4.1`, …). You don't deploy these; Voice Live hosts them. The
default matrix exercises one realtime baseline, three text-via-Voice-Live
flavours, and one own-deployment baseline against the OpenAI Realtime API:

    realtime  / gpt-realtime-1.5     ← rung 1: own-deployment Realtime API
    voicelive / gpt-realtime         ← rung 2: hosted realtime, same shape
    voicelive / gpt-realtime-mini    ← rung 2: hosted realtime, smaller
    voicelive / gpt-5-mini           ← rung 2: hosted text model + Azure TTS
    voicelive / gpt-4o-mini          ← rung 2: hosted text model + Azure TTS

Each scenario is run for `--iterations` rounds × `--turns` turns to absorb
pay-as-you-go noise. The runner collects, per turn:

    ttfa_ms          — request → first audio chunk
    ttft_ms          — request → first text/transcript token
    total_response_ms — request → response.done
    audio_duration_ms — wall-clock duration of generated audio
    audio_bytes, audio_chunks
    transcript

…and per iteration: session_setup_ms, total_runtime_ms, errors.

The output report aggregates across (iterations × turns) per scenario, so a
5-iteration × 4-turn run on each of 5 scenarios gives 20 samples per scenario
in the stats summary (min / p50 / mean / p95 / max / CoV%).

Usage:
  uv run python -m benchmark.run                       # default 5-scenario matrix
  uv run python -m benchmark.run --iterations 10       # 10 rounds, default matrix
  uv run python -m benchmark.run --scenarios voicelive:gpt-5-mini voicelive:gpt-4o
  uv run python -m benchmark.run --turns 6 --iterations 5
  uv run python -m benchmark.run --prompts my.txt
  uv run python -m benchmark.run --no-wav              # metrics only, no recordings
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import re
import sys
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import AsyncAzureOpenAI

from voicelive_demo.config import (
    azure_ad_token_provider,
    azure_agent_token_provider,
    get_settings,
)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("benchmark")

settings = get_settings()

SAMPLE_RATE = 24000
SUPPORTED_MODES = {"realtime", "voicelive", "agent"}

# Default matrix — covers the demo's narrative: own-deployment Realtime baseline,
# Voice Live hosted realtime models (same shape, drop-in URL swap), and Voice
# Live hosted *text* models (gpt-5-mini, gpt-4o-mini) wrapped with Azure TTS.
DEFAULT_SCENARIOS: list[tuple[str, str]] = [
    ("realtime",  "gpt-realtime-1.5"),
    ("voicelive", "gpt-realtime"),
    ("voicelive", "gpt-realtime-mini"),
    ("voicelive", "gpt-5-mini"),
    ("voicelive", "gpt-4o-mini"),
]

DEFAULT_PROMPTS = [
    "Hello! In one short sentence, introduce yourself.",
    "What is two plus two? Answer in one word.",
    "Tell me one short developer joke, please.",
    "What is the capital of Sweden? Reply with just the city name.",
]


# ──────────────────────────── connection plumbing ────────────────────────────

def make_session(mode: str, voice: str = "en-US-Ava:DragonHDLatestNeural") -> dict:
    """Return the session.update payload appropriate for this mode."""
    if mode == "realtime":
        return {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "voice": "alloy",  # Realtime API only accepts the OpenAI voice set
            "modalities": ["text", "audio"],
        }
    # voicelive + agent share the rich session schema
    return {
        "turn_detection": {"type": "azure_semantic_vad", "remove_filler_words": False},
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "voice": {"name": voice, "type": "azure-standard"},
        "modalities": ["text", "audio"],
        "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
        "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
        "input_audio_transcription": {"model": "azure-fast-transcription"},
    }


async def open_connection(mode: str, model: str):
    """Return the async-ctx-manager for the rung+model combination."""
    if mode == "realtime":
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_endpoint,
            api_version=settings.api_version_realtime,
            azure_ad_token_provider=azure_ad_token_provider,
        )
        return client.realtime.connect(model=model)
    if mode == "voicelive":
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_endpoint,
            api_version=settings.api_version_voicelive,
            azure_ad_token_provider=azure_ad_token_provider,
            websocket_base_url=settings.azure_voice_live_endpoint,
        )
        return client.realtime.connect(model=model, extra_query={"model": model})
    if mode == "agent":
        if not settings.agent_id or not settings.agent_project_name:
            raise RuntimeError("mode=agent needs AGENT_ID + AGENT_PROJECT_NAME in .env.")
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_endpoint,
            api_version=settings.api_version_voicelive,
            azure_ad_token_provider=azure_ad_token_provider,
            websocket_base_url=settings.azure_voice_live_endpoint,
        )
        token = await azure_agent_token_provider()
        return client.realtime.connect(
            model=model,
            extra_query={
                "agent-id":           settings.agent_id,
                "agent-project-name": settings.agent_project_name,
                "agent-access-token": token,
            },
        )
    raise ValueError(f"unknown mode: {mode!r}")


# ──────────────────────────── per-turn collection ────────────────────────────

async def collect_until_done(conn, *, t_request: float, timeout: float = 45.0) -> dict:
    audio_chunks: list[bytes] = []
    transcript_chunks: list[str] = []
    t_first_audio: float | None = None
    t_first_text: float | None = None
    audio_bytes = 0
    error_msg: str | None = None
    deadline = t_request + timeout

    async for evt in conn:
        if time.perf_counter() > deadline:
            error_msg = f"timeout after {timeout}s"
            break
        etype = getattr(evt, "type", "?")
        now = time.perf_counter()

        if etype in ("response.audio.delta", "response.output_audio.delta"):
            if t_first_audio is None:
                t_first_audio = now
            delta = getattr(evt, "delta", None)
            if delta:
                chunk = base64.b64decode(delta)
                audio_chunks.append(chunk)
                audio_bytes += len(chunk)
        elif etype in (
            "response.text.delta", "response.output_text.delta",
            "response.audio_transcript.delta", "response.output_audio_transcript.delta",
        ):
            if t_first_text is None:
                t_first_text = now
            delta = getattr(evt, "delta", None) or ""
            transcript_chunks.append(delta)
        elif etype in (
            "response.audio_transcript.done", "response.output_audio_transcript.done",
        ):
            full = getattr(evt, "transcript", None)
            if full and not transcript_chunks:
                transcript_chunks.append(full)
        elif etype == "response.done":
            break
        elif etype == "error":
            err = getattr(evt, "error", None)
            error_msg = getattr(err, "message", str(err)) if err else "unknown error"
            break

    t_done = time.perf_counter()
    audio_data = b"".join(audio_chunks)
    duration_ms = (len(audio_data) // 2) / SAMPLE_RATE * 1000
    return {
        "ttfa_ms": round((t_first_audio - t_request) * 1000) if t_first_audio else None,
        "ttft_ms": round((t_first_text - t_request) * 1000) if t_first_text else None,
        "total_response_ms": round((t_done - t_request) * 1000),
        "audio_duration_ms": round(duration_ms),
        "audio_bytes": audio_bytes,
        "audio_chunks": len(audio_chunks),
        "transcript": "".join(transcript_chunks).strip(),
        "audio_data": audio_data,
        "error": error_msg,
    }


# ──────────────────────────── one iteration ────────────────────────────

async def run_iteration(
    mode: str, model: str, prompts: list[str], *,
    iteration: int, scenario_slug: str, out_dir: Path, save_wav: bool,
) -> dict:
    iteration_metrics: dict[str, Any] = {
        "iteration": iteration,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "session_setup_ms": None,
        "session_id": None,
        "turns": [],
        "total_runtime_ms": None,
        "error": None,
    }

    t_start = time.perf_counter()
    try:
        mgr = await open_connection(mode, model)
        async with mgr as conn:
            await conn.session.update(session=make_session(mode))
            # Drain to session.updated so the timer reflects ready-to-respond
            async for evt in conn:
                etype = getattr(evt, "type", "?")
                if etype == "session.created":
                    sess = getattr(evt, "session", None)
                    iteration_metrics["session_id"] = (
                        getattr(sess, "id", None) if sess else None
                    )
                elif etype == "session.updated":
                    break
                elif etype == "error":
                    err = getattr(evt, "error", None)
                    iteration_metrics["error"] = (
                        getattr(err, "message", str(err)) if err else "unknown error"
                    )
                    return iteration_metrics
            iteration_metrics["session_setup_ms"] = round((time.perf_counter() - t_start) * 1000)

            for i, prompt in enumerate(prompts, 1):
                await conn.conversation.item.create(item={
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                })
                t_request = time.perf_counter()
                await conn.response.create(response={"modalities": ["audio", "text"]})
                turn = await collect_until_done(conn, t_request=t_request)
                audio_data = turn.pop("audio_data")

                wav_name = None
                if save_wav and audio_data:
                    wav_name = f"{scenario_slug}_iter{iteration:02d}_turn{i:02d}.wav"
                    with wave.open(str(out_dir / wav_name), "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(SAMPLE_RATE)
                        wav.writeframes(audio_data)

                turn.update({"turn": i, "prompt": prompt, "wav_file": wav_name})
                iteration_metrics["turns"].append(turn)
                err_tag = f"  ⚠ {turn['error']}" if turn["error"] else ""
                print(
                    f"    iter {iteration} turn {i}: "
                    f"ttfa={turn['ttfa_ms']}ms  "
                    f"ttft={turn['ttft_ms']}ms  "
                    f"total={turn['total_response_ms']}ms  "
                    f"audio={turn['audio_duration_ms']}ms"
                    f"{err_tag}",
                    flush=True,
                )
    except Exception as e:
        iteration_metrics["error"] = f"{type(e).__name__}: {e}"
        logger.exception("[%s/%s iter %d] failed", mode, model, iteration)

    iteration_metrics["total_runtime_ms"] = round((time.perf_counter() - t_start) * 1000)
    return iteration_metrics


# ──────────────────────────── per-scenario driver ────────────────────────────

def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9.-]+", "-", text).strip("-").lower()


async def run_scenario(
    mode: str, model: str, *,
    prompts: list[str], iterations: int, out_dir: Path, save_wav: bool,
    inter_iteration_delay_s: float = 0.5,
) -> dict:
    label = f"{mode}/{model}"
    slug = _slug(label)
    api_version = (
        settings.api_version_realtime if mode == "realtime"
        else settings.api_version_voicelive
    )
    print(f"\n=== {label}  (api-version={api_version}, {iterations} iter × {len(prompts)} turns) ===",
          flush=True)

    scenario = {
        "label": label,
        "slug": slug,
        "mode": mode,
        "model": model,
        "api_version": api_version,
        "endpoint": settings.azure_endpoint,
        "iterations": [],
    }
    for it in range(1, iterations + 1):
        result = await run_iteration(
            mode, model, prompts,
            iteration=it, scenario_slug=slug, out_dir=out_dir, save_wav=save_wav,
        )
        scenario["iterations"].append(result)
        if it < iterations and inter_iteration_delay_s > 0:
            await asyncio.sleep(inter_iteration_delay_s)
    return scenario


# ──────────────────────────── aggregation ────────────────────────────

def _stats(values: list[Any]) -> dict[str, Any]:
    vals = sorted(v for v in values if isinstance(v, (int, float)))
    if not vals:
        return {"n": 0, "min": None, "p50": None, "mean": None, "p95": None, "max": None,
                "stdev_pct": None}
    n = len(vals)
    p50 = vals[int(n * 0.5) if n > 1 else 0]
    p95 = vals[min(n - 1, int(n * 0.95))]
    mean = sum(vals) / n
    # coefficient of variation as % — useful to see noise level
    if n > 1 and mean:
        var = sum((v - mean) ** 2 for v in vals) / (n - 1)
        cv = round(100 * (var ** 0.5) / mean, 1)
    else:
        cv = None
    return {
        "n": n,
        "min": vals[0],
        "p50": p50,
        "mean": round(mean, 1),
        "p95": p95,
        "max": vals[-1],
        "stdev_pct": cv,
    }


def _flat_turn_values(scenario: dict, key: str) -> list[Any]:
    return [
        t.get(key)
        for it in scenario["iterations"]
        for t in it.get("turns", [])
    ]


def _session_setup_values(scenario: dict) -> list[Any]:
    return [it.get("session_setup_ms") for it in scenario["iterations"]]


def build_comparison_md(scenarios: list[dict], prompts: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Voice Live benchmark — scenario matrix × iterations\n")
    lines.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n")

    iters = max((len(s["iterations"]) for s in scenarios), default=0)
    turns = max(
        (len(it.get("turns", [])) for s in scenarios for it in s["iterations"]),
        default=0,
    )
    lines.append(f"**Matrix:** {len(scenarios)} scenarios × {iters} iterations × {turns} turns "
                 f"⇒ {iters * turns} samples per scenario.\n")

    # Prompts used
    lines.append("**Prompt script:**\n")
    for i, p in enumerate(prompts, 1):
        lines.append(f"{i}. _{p}_")
    lines.append("")

    # Per-scenario headline table
    lines.append("## Headline — per-scenario aggregates\n")
    lines.append("| Scenario | api-version | TTFA p50 | TTFA p95 | TTFT p50 | Total p50 | Audio dur p50 | Session setup p50 | Errors |")
    lines.append("|----------|-------------|--------:|--------:|--------:|---------:|-------------:|-----------------:|------:|")
    for s in scenarios:
        ttfa = _stats(_flat_turn_values(s, "ttfa_ms"))
        ttft = _stats(_flat_turn_values(s, "ttft_ms"))
        total = _stats(_flat_turn_values(s, "total_response_ms"))
        audio = _stats(_flat_turn_values(s, "audio_duration_ms"))
        setup = _stats(_session_setup_values(s))
        n_errors = sum(
            1 for it in s["iterations"]
            for t in it.get("turns", []) if t.get("error")
        ) + sum(1 for it in s["iterations"] if it.get("error"))
        lines.append(
            f"| **`{s['label']}`** | `{s['api_version']}` "
            f"| {ttfa['p50']} ms | {ttfa['p95']} ms "
            f"| {ttft['p50']} ms | {total['p50']} ms "
            f"| {audio['p50']} ms | {setup['p50']} ms | {n_errors} |"
        )
    lines.append("")

    # Full stats per scenario
    lines.append("## Full stats per scenario (across all iterations × turns)\n")
    lines.append("| Scenario | Metric | n | min | p50 | mean | p95 | max | CoV% |")
    lines.append("|----------|--------|--:|----:|----:|-----:|----:|----:|----:|")
    for s in scenarios:
        for key, label in (
            ("ttfa_ms",            "TTFA (ms)"),
            ("ttft_ms",            "TTFT (ms)"),
            ("total_response_ms",  "Total response (ms)"),
            ("audio_duration_ms",  "Audio dur (ms)"),
            ("audio_chunks",       "Audio chunks"),
        ):
            st = _stats(_flat_turn_values(s, key))
            lines.append(
                f"| `{s['label']}` | {label} | {st['n']} | {st['min']} | {st['p50']} "
                f"| {st['mean']} | {st['p95']} | {st['max']} | {st['stdev_pct']} |"
            )
        st = _stats(_session_setup_values(s))
        lines.append(
            f"| `{s['label']}` | Session setup (ms) | {st['n']} | {st['min']} | {st['p50']} "
            f"| {st['mean']} | {st['p95']} | {st['max']} | {st['stdev_pct']} |"
        )
    lines.append("")

    # Per-iteration drill-down (for noise diagnosis)
    lines.append("## Per-iteration drill-down — TTFA per turn (ms)\n")
    turn_headers = " | ".join(f"T{i+1}" for i in range(turns))
    turn_sep = " | ".join(["------:"] * turns)
    for s in scenarios:
        lines.append(f"### `{s['label']}`\n")
        lines.append(f"| Iter | Setup | {turn_headers} | Errors |")
        lines.append(f"|-----:|------:| {turn_sep} |-------:|")
        for it in s["iterations"]:
            ttfa_cols: list[str] = []
            for i in range(turns):
                if i < len(it.get("turns", [])):
                    v = it["turns"][i].get("ttfa_ms")
                    ttfa_cols.append(f"{v}" if v is not None else "—")
                else:
                    ttfa_cols.append("—")
            n_errs = (1 if it.get("error") else 0) + sum(
                1 for t in it.get("turns", []) if t.get("error")
            )
            lines.append(
                f"| {it['iteration']} | {it.get('session_setup_ms', '—')} "
                f"| {' | '.join(ttfa_cols)} | {n_errs} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("\n_Caveats: text-input bypasses VAD / STT / echo cancellation, "
                 "so these are a **lower bound** on real-world latency. They're "
                 "still useful apples-to-apples since every scenario uses the "
                 "identical flow. Voice Live wraps text models (gpt-5-mini, "
                 "gpt-4o-mini, …) with Azure TTS, so audio duration tracks text "
                 "length more loosely than a native realtime model. CoV% = "
                 "coefficient of variation across samples — a noise indicator "
                 "(PAYG can drift)._")
    return "\n".join(lines) + "\n"


# ──────────────────────────── CLI ────────────────────────────

def parse_scenario(s: str) -> tuple[str, str]:
    if ":" not in s:
        raise argparse.ArgumentTypeError(f"expected mode:model, got {s!r}")
    mode, _, model = s.partition(":")
    mode = mode.strip().lower()
    model = model.strip()
    if mode not in SUPPORTED_MODES:
        raise argparse.ArgumentTypeError(f"unknown mode {mode!r}; expected one of {SUPPORTED_MODES}")
    if not model:
        raise argparse.ArgumentTypeError("model must not be empty")
    return mode, model


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--scenarios", nargs="+", type=parse_scenario, default=None,
        metavar="MODE:MODEL",
        help="Override the default scenario matrix. Each item is `mode:model`.",
    )
    p.add_argument("--iterations", type=int, default=3,
                   help="How many times to repeat each scenario (default: 3).")
    p.add_argument("--turns", type=int, default=len(DEFAULT_PROMPTS),
                   help="Turns per iteration (default: 4).")
    p.add_argument("--prompts", type=Path, default=None,
                   help="Optional file with one prompt per line; overrides defaults.")
    p.add_argument("--out", type=Path, default=None,
                   help="Output directory (default: benchmark/results/<timestamp>).")
    p.add_argument("--no-wav", action="store_true",
                   help="Don't save WAV recordings (metrics-only run).")
    args = p.parse_args()

    scenarios = args.scenarios or DEFAULT_SCENARIOS

    prompts = (
        [ln.strip() for ln in args.prompts.read_text().splitlines() if ln.strip()]
        if args.prompts else list(DEFAULT_PROMPTS)
    )
    if args.turns < len(prompts):
        prompts = prompts[: args.turns]
    elif args.turns > len(prompts):
        prompts = (prompts * ((args.turns // len(prompts)) + 1))[: args.turns]

    out_dir = args.out or (
        Path(__file__).resolve().parent / "results"
        / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output:      {out_dir}", flush=True)
    print(f"Scenarios:   {len(scenarios)} ({', '.join(f'{m}:{md}' for m, md in scenarios)})", flush=True)
    print(f"Iterations:  {args.iterations} per scenario", flush=True)
    print(f"Turns:       {len(prompts)} per iteration", flush=True)
    print(f"WAVs:        {'off' if args.no_wav else 'on'}", flush=True)

    results: list[dict] = []
    for mode, model in scenarios:
        s = await run_scenario(
            mode, model,
            prompts=prompts,
            iterations=args.iterations,
            out_dir=out_dir,
            save_wav=not args.no_wav,
        )
        results.append(s)

    (out_dir / "metrics.json").write_text(json.dumps(results, indent=2))
    (out_dir / "comparison.md").write_text(build_comparison_md(results, prompts))

    print("\n=== Done ===")
    print(f"  JSON:    {out_dir / 'metrics.json'}")
    print(f"  Report:  {out_dir / 'comparison.md'}")
    if not args.no_wav:
        print(f"  WAVs:    {len(list(out_dir.glob('*.wav')))} files in {out_dir}")

    # Exit non-zero if any iteration died at the session level
    any_error = any(it.get("error") for s in results for it in s["iterations"])
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
