## Voice Live Gradio Demo — Changelog

<a name="0.4.0"></a>
# 0.4.0 (2026-06-04)

*Features*
* **Deployable web shell** — new `app_web.py` + `voicelive_demo/web_server.py`
  ship a FastAPI + vanilla-JS + WebSocket variant that streams raw
  24 kHz PCM16 frames over WSS. Drops the Gradio + FastRTC + WebRTC
  stack so the demo can deploy on any L7-only container platform
  (Azure Container Apps, App Service, Cloud Run) without TURN.
* **`azd up` template** — `azure.yaml` + `infra/` ship Bicep for the
  full footprint: UAMI, ACR, Log Analytics, ACA env + app, AcrPull,
  Cognitive Services User + Azure AI User on a BYO Foundry resource.
  RBAC pre-empts the AcrPull propagation race via `dependsOn: [rbac]`.
  All values are sourced from `azd env set …` — no internal resource
  names hardcoded in tracked files.
* **`docs/AZURE_DEPLOY.md`** — peer-facing one-page walkthrough with
  tenant-isolation guidance, env-var checklist, verify gate, and the
  browser-support matrix.

*Notes*
* The Gradio + FastRTC shell (`app.py`, `app_demo.py`, `app_*.py`)
  is unchanged — use it for local-only development and screen-share
  demos where TURN is a non-issue.
* The web shell intentionally re-imports `voicelive_demo.handler` so
  it shares the same `SharedState` dataclass + event-switching logic
  as the Gradio shell. This keeps the rungs in lockstep across both
  front-ends; the trade-off is a larger container image because
  Gradio + FastRTC + NumPy still pull in transitively.

<a name="0.3.0"></a>
# 0.3.0 (2026-05-27)

*Features*
* **Unified `demo` mode** (`app_demo.py`) — a runtime rung switcher that
  surfaces all three rungs (Realtime / Voice Live / Voice Live + Agent)
  inside a single Gradio app, with a primary-button row at the top of
  the Talk tab and live destination/endpoint badges that update on
  switch. `MODE=demo` is now the default in `.env.example`.
* **Italian localization** — `voicelive_demo/i18n.py` ships parallel
  English + Italian string tables; a globe-icon language switcher in
  the top-right toggles UI copy, voice catalog defaults, and system
  instructions. Voice Live default voice swaps to `it-IT-Isabella` for
  Italian.
* **About tab** — generic, customer-neutral explainer covering
  Realtime vs Voice Live positioning, GA timeline, and links to the
  official Microsoft docs (no bespoke FAQ content lifted from any
  customer conversation).

*Bug Fixes*
* **Mode-aware voice picker** — Realtime mode now exposes only the 10
  OpenAI voices the API actually accepts (`alloy`, `ash`, `ballad`,
  `coral`, `echo`, `sage`, `shimmer`, `verse`, `marin`, `cedar`);
  Voice Live / Agent expose the Azure Neural HD catalog per locale.
  Previously the picker offered Azure HD voices in Realtime mode and
  the rung silently substituted `alloy` regardless of selection.
* **Endpoint configurability** — every endpoint, api-version, agent
  identifier, sovereign-cloud scope, and bind address is now driven by
  `.env` (`AZURE_OPENAI_ENDPOINT`, `AZURE_VOICELIVE_ENDPOINT`,
  `AZURE_OPENAI_API_VERSION`, `AZURE_VOICELIVE_API_VERSION`,
  `AGENT_PROJECT_NAME`, `AGENT_ID`, `AZURE_COGNITIVE_SERVICES_SCOPE`,
  `AZURE_AI_SCOPE`, `HOST`, `PORT`). No hardcoded resource names.
* **Benchmark resource cleanup** — credential + per-rung
  `AsyncAzureOpenAI` client get `close()`d in a `finally` block; no
  more aiohttp "Unclosed client session" warnings on exit.
* **Diff page** — the Switch tab now reformats sources to strip
  whitespace noise and only highlights the per-function deltas that
  matter (kwargs into `client.realtime.connect`). Decorator +
  try/finally scaffolding is identical across rungs so it doesn't
  pollute the diff.

*Refactors*
* **Zero benchmark duplication** — every rung's `connect_factory` is
  now an `@asynccontextmanager` that owns the full client + connection
  lifecycle (open `AsyncAzureOpenAI`, enter `realtime.connect(...)`,
  `await client.close()` on exit) and accepts an optional `model=`
  keyword for benchmark overrides. The handler and the benchmark both
  consume `REGISTRY[Mode(...)]` and do `async with rung.connect_factory()
  as conn: …` — there is **no** mode branching outside the three rung
  files (`grep -E 'if mode ==' handler.py app_*.py benchmark/run.py`
  returns nothing connection-related).
* **Event-handling clarification** — `handler._handle_event()` carries
  a comment block stating explicitly that all three rungs speak the
  OpenAI Realtime event schema end-to-end, and that the dual
  `response.audio.*` / `response.output_audio.*` handling is an SDK
  preview→GA migration shim, **not** mode-divergence.

*Docs*
* `README.md` rewritten with explicit sections for Quickstart,
  Configuration, Switching rungs, Localization, Auth, Benchmark, and
  Troubleshooting (`az login` tenant scoping, `pyaudio` build notes,
  port 7860 conflicts).
* `AGENTS.md` — public-repo discipline rules + branching protocol for
  any AI coding agent working in this repo.

<a name="0.2.0"></a>
# 0.2.0 (2026-05-25)

*Features*
* **Three sibling app files** (`app_realtime.py`, `app_voicelive.py`,
  `app_agent.py`) that share **all** plumbing via the new
  `voicelive_demo/` package — the three files differ *only* in the
  connection-setup block, which is the actual punchline of the demo.
* **Benchmark harness** (`benchmark/run.py`) — runs a scenario matrix
  (mode × model) × `--iterations` × `--turns` to absorb PAYG noise.
  Default matrix covers the Realtime baseline + Voice Live's hosted
  realtime *and* text-model flavours (`gpt-realtime`,
  `gpt-realtime-mini`, `gpt-5-mini`, `gpt-4o-mini`). Emits
  `metrics.json` + `comparison.md` (headline aggregates, full stats
  with p50/p95/CoV%, per-iteration drill-down) + per-turn WAVs.
* `app.py` is now a thin dispatcher selecting one of the three based on
  the `MODE` env var (`realtime` | `voicelive` | `agent`).
* New Gradio Blocks UI: header MODE/MODEL/ENDPOINT chip, live status
  badge (Idle → Connecting → Listening 🎙️ → Thinking → Speaking 🔊 →
  Error), curated voice picker (Azure Neural HD + OpenAI voices), system
  instructions textbox, reset button, connection-details accordion.
* New **🧩 View the diff** tab — renders the two key diffs (rung 1 ↔ rung 2
  and rung 2 ↔ rung 3) side-by-side via `difflib.HtmlDiff`, computed
  from the live source files.
* New **ℹ️ About** tab with per-rung notes + GA-timeline rationale.

*Bug Fixes*
* Migrated off the deprecated `client.beta.realtime.connect` to the GA
  `client.realtime.connect` call shape (beta path sunsets after
  2026-04-30).
* Default model name in `.env.example` was `gpt-4.1` (a text model);
  it is now `gpt-realtime-1.5`, the newest realtime model Voice Live
  serves in Sweden Central as of May 2026.
* Pinned `av>=16.0.0,<17.0.0` to use prebuilt wheels (the older
  `av==14.x` won't build against `ffmpeg 8.x`).

*Breaking Changes*
* `MODE` values changed: `"UI"` → one of `realtime`, `voicelive`,
  `agent`.
* `.env` schema changed: `AZURE_VOICE_LIVE_ENDPOINT` →
  `AZURE_VOICELIVE_ENDPOINT`; new optional `AZURE_VOICELIVE_API_VERSION`
  (defaults to `2025-10-01`).
* Top-level `config.py` removed; settings live in
  `voicelive_demo/config.py`.
* `openai>=2.0.0` and `fastrtc>=0.0.34` required.
* Dropped the redundant `dotenv` dep (pydantic-settings reads `.env`).
* Removed all references to API keys — auth is **Entra ID only**, via
  `azure.identity.aio.DefaultAzureCredential`.

<a name="0.1.0"></a>
# 0.1.0 (2025 — initial release)

*Features*
* Single `app.py` demonstrating Voice Live as a drop-in over OpenAI
  Realtime, using `openai==1.x` `client.beta.realtime.connect`.
* Optional Foundry-Agent branch toggled via the presence of `AGENT_ID`.

