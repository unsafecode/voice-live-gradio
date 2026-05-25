## Voice Live Gradio Demo — Changelog

<a name="0.2.0"></a>
# 0.2.0 (2026-05-25)

*Features*
* **Three sibling app files** (`app_realtime.py`, `app_voicelive.py`,
  `app_agent.py`) that share **all** plumbing via the new
  `voicelive_demo/` package — the three files differ *only* in the
  connection-setup block, which is the actual punchline of the demo.
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

