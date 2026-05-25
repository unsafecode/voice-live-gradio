"""Benchmark runner — same conversation across rungs, with recordings + metrics.

Reuses each rung's `connect_factory` + `make_session` so the benchmark is
hitting *exactly* the code path the demo uses. Sends a fixed conversation
script via text-input mode (deterministic, no STT variance) and asks the
model for audio responses.

Per turn we capture:
  * ttfa_ms          — time from response.create → first audio chunk
  * ttft_ms          — time from response.create → first text/transcript token
  * total_response_ms — time from response.create → response.done
  * audio_duration_ms — wall-clock duration of the generated audio
  * audio_bytes      — raw PCM16 byte count
  * audio_chunks     — number of audio.delta events
  * transcript       — assembled assistant transcript

Per session we also capture:
  * session_setup_ms — time from connect_factory() → session.updated received
  * total_runtime_ms — wall clock for the whole rung

Output:
  benchmark/results/<timestamp>/
    ├── metrics.json
    ├── comparison.md
    ├── <mode>_turn_1.wav
    ├── <mode>_turn_2.wav
    └── …

Usage:
  uv run python -m benchmark.run                       # all modes
  uv run python -m benchmark.run --modes realtime      # one mode
  uv run python -m benchmark.run --turns 5             # custom turn count
  uv run python -m benchmark.run --prompts prompts.txt # custom prompts file

Note: text-input mode bypasses VAD / STT / echo cancellation, so the
numbers are a *lower bound* on real-world latency. They're still useful
for apples-to-apples comparison across rungs because the same flow is
used everywhere.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import importlib
import json
import logging
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("benchmark")

MODE_MODULES = {
    "realtime":  "app_realtime",
    "voicelive": "app_voicelive",
    "agent":     "app_agent",
}

DEFAULT_PROMPTS = [
    "Hello! In one short sentence, introduce yourself.",
    "What is two plus two? Answer in one word.",
    "Tell me one short developer joke, please.",
    "What is the capital of Sweden? Reply with just the city name.",
]

SAMPLE_RATE = 24000


async def collect_until_done(conn, *, t_request: float, turn_timeout: float = 30.0) -> dict:
    """Drain events for one turn and return per-turn metrics + assembled audio."""
    audio_chunks: list[bytes] = []
    transcript_chunks: list[str] = []
    t_first_audio: float | None = None
    t_first_text: float | None = None
    audio_bytes = 0
    error_msg: str | None = None
    deadline = t_request + turn_timeout

    async for evt in conn:
        if time.perf_counter() > deadline:
            error_msg = f"timeout after {turn_timeout}s"
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


async def run_mode(mode: str, prompts: list[str], out_dir: Path) -> dict:
    print(f"\n=== {mode} ({len(prompts)} turns) ===", flush=True)
    module = importlib.import_module(MODE_MODULES[mode])
    connect_factory = module.connect_factory
    make_session = module.make_session
    shared = module.SHARED
    settings = module.settings

    metrics = {
        "mode": mode,
        "model": settings.azure_deployment_name,
        "endpoint": settings.azure_endpoint,
        "api_version": (
            settings.api_version_realtime if mode == "realtime"
            else settings.api_version_voicelive
        ),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "session_setup_ms": None,
        "session_id": None,
        "turns": [],
        "total_runtime_ms": None,
        "error": None,
    }

    t_start = time.perf_counter()
    try:
        mgr = await connect_factory()
        async with mgr as conn:
            await conn.session.update(session=make_session(shared))

            # Drain until session is created+updated so the timer reflects ready-to-respond.
            async for evt in conn:
                etype = getattr(evt, "type", "?")
                if etype == "session.created":
                    sess = getattr(evt, "session", None)
                    metrics["session_id"] = getattr(sess, "id", None) if sess else None
                elif etype == "session.updated":
                    break
                elif etype == "error":
                    err = getattr(evt, "error", None)
                    metrics["error"] = getattr(err, "message", str(err)) if err else "unknown error"
                    return metrics
            metrics["session_setup_ms"] = round((time.perf_counter() - t_start) * 1000)
            print(f"  session ready in {metrics['session_setup_ms']}ms", flush=True)

            for i, prompt in enumerate(prompts, 1):
                await conn.conversation.item.create(
                    item={
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    }
                )
                t_request = time.perf_counter()
                await conn.response.create(response={"modalities": ["audio", "text"]})
                turn = await collect_until_done(conn, t_request=t_request)
                audio_data = turn.pop("audio_data")

                wav_path = out_dir / f"{mode}_turn_{i:02d}.wav"
                if audio_data:
                    with wave.open(str(wav_path), "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(SAMPLE_RATE)
                        wav.writeframes(audio_data)
                    turn["wav_file"] = wav_path.name
                else:
                    turn["wav_file"] = None

                turn["turn"] = i
                turn["prompt"] = prompt
                metrics["turns"].append(turn)
                err_tag = f"  ⚠ {turn['error']}" if turn["error"] else ""
                print(
                    f"  turn {i}: ttfa={turn['ttfa_ms']}ms  "
                    f"ttft={turn['ttft_ms']}ms  "
                    f"total={turn['total_response_ms']}ms  "
                    f"audio={turn['audio_duration_ms']}ms ({turn['audio_chunks']} chunks)"
                    f"{err_tag}",
                    flush=True,
                )
    except Exception as e:
        metrics["error"] = f"{type(e).__name__}: {e}"
        logger.exception("[%s] benchmark failed", mode)

    metrics["total_runtime_ms"] = round((time.perf_counter() - t_start) * 1000)
    return metrics


def _stats(values: list[int | float | None]) -> dict:
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return {"n": 0, "min": None, "p50": None, "mean": None, "max": None}
    s = sorted(vals)
    n = len(s)
    return {
        "n": n,
        "min": s[0],
        "p50": s[n // 2],
        "mean": round(sum(s) / n, 1),
        "max": s[-1],
    }


def build_comparison_md(results: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Voice Live benchmark comparison\n")
    lines.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n")
    lines.append("## Per-mode totals\n")
    lines.append("| Mode | Model | api-version | Session setup | Total runtime | Turns | Errors |")
    lines.append("|------|-------|-------------|--------------:|--------------:|------:|-------:|")
    for r in results:
        err_count = sum(1 for t in r.get("turns", []) if t.get("error")) + (1 if r.get("error") else 0)
        lines.append(
            f"| `{r['mode']}` | `{r['model']}` | `{r['api_version']}` "
            f"| {r.get('session_setup_ms', '—')} ms "
            f"| {r.get('total_runtime_ms', '—')} ms "
            f"| {len(r.get('turns', []))} | {err_count} |"
        )

    lines.append("\n## Per-turn latency (ms) — TTFA = time-to-first-audio\n")
    for r in results:
        lines.append(f"### `{r['mode']}`\n")
        if r.get("error"):
            lines.append(f"⚠️ **session error:** {r['error']}\n")
        lines.append("| Turn | Prompt | TTFA | TTFT | Total | Audio dur | Audio chunks | Transcript |")
        lines.append("|----:|--------|----:|----:|------:|---------:|------------:|------------|")
        for t in r.get("turns", []):
            prompt = (t["prompt"][:48] + "…") if len(t["prompt"]) > 50 else t["prompt"]
            transcript = (t["transcript"][:70] + "…") if len(t["transcript"]) > 72 else t["transcript"]
            err = f" ⚠ {t['error']}" if t.get("error") else ""
            lines.append(
                f"| {t['turn']} | _{prompt}_ "
                f"| {t['ttfa_ms']} | {t['ttft_ms']} | {t['total_response_ms']} "
                f"| {t['audio_duration_ms']} | {t['audio_chunks']} "
                f"| {transcript}{err} |"
            )
        lines.append("")

    lines.append("## Stats summary (across turns, per mode)\n")
    lines.append("| Mode | Metric | n | min | p50 | mean | max |")
    lines.append("|------|--------|--:|----:|----:|-----:|----:|")
    for r in results:
        for key, label in (
            ("ttfa_ms", "TTFA (ms)"),
            ("ttft_ms", "TTFT (ms)"),
            ("total_response_ms", "Total (ms)"),
            ("audio_duration_ms", "Audio dur (ms)"),
        ):
            s = _stats([t.get(key) for t in r.get("turns", [])])
            lines.append(
                f"| `{r['mode']}` | {label} | {s['n']} | {s['min']} | {s['p50']} | {s['mean']} | {s['max']} |"
            )

    lines.append("\n---")
    lines.append("\n_Caveats: text-input bypasses VAD / STT / echo cancellation, so these "
                 "numbers are a **lower bound** on real-world latency. They're still useful "
                 "apples-to-apples since every rung uses the identical flow. Run with "
                 "`--turns N` for more samples per mode._")
    return "\n".join(lines) + "\n"


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--modes", nargs="+", default=["realtime", "voicelive"],
        choices=list(MODE_MODULES.keys()),
        help="Which rungs to benchmark. Default: realtime + voicelive (agent requires AGENT_ID).",
    )
    p.add_argument("--turns", type=int, default=len(DEFAULT_PROMPTS),
                   help="Number of turns per rung (truncates/repeats prompts as needed).")
    p.add_argument("--prompts", type=Path, default=None,
                   help="Optional file with one prompt per line; overrides defaults.")
    p.add_argument("--out", type=Path, default=None,
                   help="Output directory (default: benchmark/results/<timestamp>).")
    args = p.parse_args()

    if args.prompts:
        prompts = [ln.strip() for ln in args.prompts.read_text().splitlines() if ln.strip()]
    else:
        prompts = list(DEFAULT_PROMPTS)
    if args.turns < len(prompts):
        prompts = prompts[: args.turns]
    elif args.turns > len(prompts):
        prompts = (prompts * ((args.turns // len(prompts)) + 1))[: args.turns]

    out_dir = args.out or (
        Path(__file__).resolve().parent / "results"
        / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output: {out_dir}", flush=True)
    print(f"Modes:  {', '.join(args.modes)}", flush=True)
    print(f"Turns:  {len(prompts)}", flush=True)

    results: list[dict] = []
    for mode in args.modes:
        try:
            m = await run_mode(mode, prompts, out_dir)
        except Exception as e:
            logger.exception("[%s] failed at top level", mode)
            m = {"mode": mode, "error": f"{type(e).__name__}: {e}", "turns": []}
        results.append(m)

    (out_dir / "metrics.json").write_text(json.dumps(results, indent=2))
    (out_dir / "comparison.md").write_text(build_comparison_md(results))

    print("\n=== Results ===")
    print(f"  JSON:    {out_dir / 'metrics.json'}")
    print(f"  Report:  {out_dir / 'comparison.md'}")
    print(f"  WAVs:    {len(list(out_dir.glob('*.wav')))} files in {out_dir}")
    return 0 if not any(r.get("error") for r in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
