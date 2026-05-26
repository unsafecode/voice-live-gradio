"""Gradio Blocks UI for the demo.

The single place where presentation lives. The three `app_*.py` files at
the repo root pass in their connection details; this module renders a
consistent, branded UI on top.
"""
from __future__ import annotations

from typing import Any

import gradio as gr
from fastrtc import WebRTC

from voicelive_demo.config import Mode
from voicelive_demo.diff_assets import render_diffs_html
from voicelive_demo.handler import SharedState, StatusEvent

MODE_LABELS = {
    Mode.REALTIME:  ("rung 1 · Azure OpenAI Realtime",       "#0078D4"),
    Mode.VOICELIVE: ("rung 2 · Azure Voice Live",            "#107C10"),
    Mode.AGENT:     ("rung 3 · Voice Live + Foundry Agent",  "#7719AA"),
}

STATUS_PALETTE = {
    "idle":       ("Idle",        "#6c757d"),
    "connecting": ("Connecting",  "#0d6efd"),
    "listening":  ("Listening",   "#d63384"),
    "thinking":   ("Thinking",    "#fd7e14"),
    "speaking":   ("Speaking",    "#198754"),
    "error":      ("Error",       "#dc3545"),
}

VOICE_OPTIONS = [
    ("Ava — Azure Neural HD (default)",       "en-US-Ava:DragonHDLatestNeural"),
    ("Jenny — Azure Neural HD",               "en-US-Jenny:DragonHDLatestNeural"),
    ("Davis — Azure Neural HD",               "en-US-Davis:DragonHDLatestNeural"),
    ("Guy — Azure Neural",                    "en-US-GuyNeural"),
    ("Brian — Azure Neural",                  "en-US-BrianNeural"),
    ("Alloy — OpenAI",                        "alloy"),
    ("Nova — OpenAI",                         "nova"),
    ("Shimmer — OpenAI",                      "shimmer"),
]


def _header_html(mode: Mode, model: str, endpoint: str) -> str:
    mode_label, mode_color = MODE_LABELS[mode]
    short_endpoint = endpoint.replace("wss://", "").replace("https://", "").split("/")[0]
    return f"""
<div class="vl-header">
  <div class="vl-header-main">
    <div class="vl-title">Voice Live <span class="vl-title-thin">Gradio Demo</span></div>
    <div class="vl-subtitle">A drop-in switch from Azure OpenAI Realtime to Azure AI Foundry Voice Live.</div>
  </div>
  <div class="vl-chips">
    <div class="vl-chip">
      <span class="vl-chip-dot" style="background:{mode_color};"></span>
      <span class="vl-chip-label">MODE</span>
      <span class="vl-chip-value">{mode_label}</span>
    </div>
    <div class="vl-chip">
      <span class="vl-chip-label">MODEL</span>
      <span class="vl-chip-value vl-mono">{model}</span>
    </div>
    <div class="vl-chip">
      <span class="vl-chip-label">ENDPOINT</span>
      <span class="vl-chip-value vl-mono">{short_endpoint}</span>
    </div>
  </div>
</div>
"""


def _status_html(status: str = "idle") -> str:
    label, color = STATUS_PALETTE.get(status, STATUS_PALETTE["idle"])
    return (
        f'<div class="vl-status" style="--status:{color};">'
        f'<span class="vl-status-dot"></span>'
        f'<span class="vl-status-label">{label}</span>'
        f'</div>'
    )


def _bind_state_outputs(chatbot: list[dict], status_html_value: str, session_info: str,
                        event: StatusEvent) -> tuple[list[dict], str, str]:
    """FastRTC additional_outputs_handler: route a StatusEvent into 3 components."""
    new_chatbot = list(chatbot or [])
    new_status = status_html_value
    new_session = session_info
    if event.kind == "message":
        new_chatbot.append({"role": event.payload["role"], "content": event.payload["content"]})
    elif event.kind == "status":
        new_status = _status_html(event.payload["status"])
    elif event.kind == "session":
        sid = event.payload.get("session_id", "?")
        model = event.payload.get("model", "?")
        new_session = f"`session_id`: `{sid}`  ·  `model`: `{model}`"
    return new_chatbot, new_status, new_session


CUSTOM_CSS = """
/* ── Reset & globals ───────────────────────────────────────────────── */
footer {display:none !important;}
.gradio-container {
    max-width: 1200px !important;
    margin: 0 auto !important;
    padding: 24px 28px 48px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", system-ui, sans-serif !important;
}
.gradio-container, .gradio-container * { box-sizing: border-box; }
body, .gradio-container { background: #f5f6f8 !important; }

/* ── Header ────────────────────────────────────────────────────────── */
.vl-header {
    background: #ffffff;
    border: 1px solid #e3e6ea;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 18px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.vl-header-main { display: flex; flex-direction: column; gap: 4px; }
.vl-title {
    font-size: 22px;
    font-weight: 600;
    color: #1a1a1a;
    letter-spacing: -0.01em;
    line-height: 1.2;
}
.vl-title-thin { font-weight: 400; color: #4a4a4a; }
.vl-subtitle { font-size: 14px; color: #5a6068; line-height: 1.4; }

.vl-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.vl-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border: 1px solid #e3e6ea;
    background: #fafbfc;
    border-radius: 8px;
    font-size: 12.5px;
}
.vl-chip-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
}
.vl-chip-label {
    color: #6a7079; font-weight: 600; letter-spacing: 0.06em; font-size: 11px;
    text-transform: uppercase;
}
.vl-chip-value { color: #1a1a1a; font-weight: 500; }
.vl-mono { font-family: "SF Mono", "Cascadia Mono", Consolas, Menlo, monospace; font-size: 12px; }

/* ── Tabs ──────────────────────────────────────────────────────────── */
.tab-nav { border-bottom: 1px solid #e3e6ea !important; margin-bottom: 18px !important; }
.tab-nav button {
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 12px 18px !important;
    color: #5a6068 !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    transition: color 0.15s ease, border-color 0.15s ease;
}
.tab-nav button.selected {
    color: #0078D4 !important;
    border-bottom-color: #0078D4 !important;
}
.tab-nav button:hover:not(.selected) { color: #1a1a1a !important; }

/* ── Cards (Gradio groups) ─────────────────────────────────────────── */
.gr-group, .gradio-container .form, fieldset {
    background: #ffffff !important;
    border: 1px solid #e3e6ea !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
}

/* Kill Gradio Soft-theme's rounded label pills everywhere.
   Gradio uses two different testids for label-style elements:
     - label[data-testid="block-label"]  (chatbot, audio, image, …)
     - span[data-testid="block-info"]    (textbox, dropdown, …) ← also rounded blue
*/
.gradio-container label[data-testid="block-label"],
.gradio-container label[data-testid="block-label"] > span,
.gradio-container span[data-testid="block-info"] {
    background: transparent !important;
    color: #2a2f36 !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 0 0 6px 0 !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}
.gradio-container label[data-testid="block-label"] > span { padding: 0 !important; }
.gradio-container span[data-testid="block-info"] { display: block; margin-bottom: 4px; }
/* Drop the cutesy feather icons Gradio prepends to every label */
.gradio-container label[data-testid="block-label"] svg { display: none !important; }

/* Hide the WebRTC widget's own "Audio" block-label entirely — the section
   heading above it already says "Microphone". */
.vl-mic-group label[data-testid="block-label"] { display: none !important; }

/* Section title + status row alignment */
.vl-status-cell { display: flex !important; justify-content: flex-end !important; align-items: center !important; }
.vl-status-cell > div { display: inline-flex; }

/* Inputs & textareas */
.gradio-container input[type="text"],
.gradio-container textarea,
.gradio-container .gr-input {
    border: 1px solid #d8dde3 !important;
    border-radius: 8px !important;
    font-size: 14px !important;
}
.gradio-container input[type="text"]:focus,
.gradio-container textarea:focus {
    border-color: #0078D4 !important;
    box-shadow: 0 0 0 3px rgba(0,120,212,0.15) !important;
}

/* Buttons */
.gradio-container button.primary, .gradio-container button[class*="primary"] {
    background: #0078D4 !important;
    border-color: #0078D4 !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}
.gradio-container button.primary:hover { background: #106ebe !important; }
.gradio-container button.secondary, .gradio-container button[class*="secondary"] {
    background: white !important;
    color: #2a2f36 !important;
    border: 1px solid #d8dde3 !important;
    border-radius: 8px !important;
}

/* ── Status pill ───────────────────────────────────────────────────── */
.vl-status {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 12px; border-radius: 999px;
    background: color-mix(in srgb, var(--status) 12%, transparent);
    color: var(--status);
    border: 1px solid color-mix(in srgb, var(--status) 35%, transparent);
    font-weight: 600; font-size: 13px;
}
.vl-status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--status);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--status) 50%, transparent);
    animation: vl-pulse 2.4s infinite;
}
@keyframes vl-pulse {
    0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--status) 60%, transparent); }
    70%  { box-shadow: 0 0 0 6px color-mix(in srgb, var(--status) 0%, transparent); }
    100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--status) 0%, transparent); }
}

/* ── Mic widget ────────────────────────────────────────────────────── */
.audio-container, .gradio-webrtc-waveContainer, .wave-container {
    position: relative !important;
    min-height: 200px;
    max-height: 320px;
}

/* ── Section headings ──────────────────────────────────────────────── */
.vl-section-title {
    font-size: 12px;
    font-weight: 700;
    color: #6a7079;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0 0 8px 0;
}
.vl-section-row { align-items: center !important; gap: 12px !important; margin-bottom: 8px !important; }
.vl-section-row > div:first-child { flex: 1; }
.vl-section-row .vl-status-cell { flex: 0 0 auto; text-align: right; }
.vl-section-row .vl-status-cell > div { display: inline-flex; }

/* Side-by-side action buttons */
.vl-button-row { gap: 8px !important; margin-top: 8px !important; }
.vl-button-row > button, .vl-button-row .gr-button { flex: 1 !important; min-width: 0 !important; }

/* ── Diff renderer ─────────────────────────────────────────────────── */
.diff-section { margin: 0 0 32px 0; }
.diff-section-title {
    display: flex; align-items: center; gap: 12px;
    font-size: 16px; font-weight: 600; color: #1a1a1a;
    margin: 0 0 8px 0;
}
.diff-step {
    display: inline-flex; align-items: center; justify-content: center;
    width: 24px; height: 24px; border-radius: 50%;
    background: #0078D4; color: white;
    font-size: 13px; font-weight: 700;
}
.diff-section-lede {
    color: #5a6068; font-size: 13.5px; line-height: 1.55;
    margin: 0 0 14px 0;
}
.diff-section-lede code {
    background: #f1f3f6; padding: 1px 6px; border-radius: 4px;
    font-family: "SF Mono", "Cascadia Mono", Consolas, Menlo, monospace;
    font-size: 12.5px; color: #2a2f36;
}

.diff-container {
    border: 1px solid #d8dde3;
    border-radius: 8px;
    overflow: hidden;
    background: white;
    font-family: "SF Mono", "Cascadia Mono", Consolas, Menlo, monospace;
    font-size: 12.5px;
    line-height: 1.55;
}
.diff-header {
    display: grid;
    grid-template-columns: 1fr 1fr;
    background: #f6f8fa;
    border-bottom: 1px solid #d8dde3;
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    font-size: 12.5px;
    font-weight: 600;
    color: #2a2f36;
}
.diff-header-side { padding: 10px 14px; }
.diff-header-side + .diff-header-side { border-left: 1px solid #d8dde3; }
.diff-body { max-height: 540px; overflow: auto; }
.diff-row {
    display: grid;
    grid-template-columns: 44px 22px 1fr 44px 22px 1fr;
    border-top: 1px solid #f0f2f5;
}
.diff-row:first-child { border-top: none; }
.diff-lno {
    padding: 1px 8px; text-align: right;
    color: #9aa0a7; user-select: none;
    border-right: 1px solid #f0f2f5;
    background: #fafbfc;
    font-size: 11.5px;
}
.diff-sign {
    padding: 1px 0; text-align: center;
    color: #6a7079; user-select: none;
    font-weight: 600;
}
.diff-code {
    padding: 1px 10px;
    white-space: pre-wrap;
    word-break: break-word;
    color: #1a1a1a;
}
/* Per-row coloring */
.diff-equal   .diff-code { background: white; }
.diff-replace .diff-code { background: #fff8c5; }
.diff-delete .diff-code:first-of-type,
.diff-delete .diff-code:nth-of-type(1) { background: #ffeef0; }
.diff-insert .diff-code:last-of-type,
.diff-insert .diff-code:nth-of-type(2) { background: #e6ffec; }
/* delete row: left side red, right side white */
.diff-delete .diff-code { background: #ffeef0; }
.diff-delete > .diff-code + .diff-lno + .diff-sign + .diff-code { background: white; }
/* insert row: left side white, right side green */
.diff-insert .diff-code { background: #e6ffec; }
.diff-insert > .diff-code { background: white; }
.diff-insert > .diff-code:last-of-type { background: #e6ffec; }
/* replace: both yellow */
.diff-replace > .diff-code:first-of-type { background: #ffeef0; }
.diff-replace > .diff-code:last-of-type { background: #e6ffec; }

.diff-sign-+ { color: #1a7f37; background: #ccffd8; }
.diff-sign-− { color: #cf222e; background: #ffd8d3; }

.diff-hunk-header {
    background: #f1f3f6;
    color: #5a6068;
    padding: 6px 14px;
    font-size: 11.5px;
    border-top: 1px solid #d8dde3;
    border-bottom: 1px solid #e3e6ea;
}
.diff-hunk-header:first-child { border-top: none; }
.diff-footer {
    padding: 8px 14px; background: #fafbfc;
    color: #6a7079; font-size: 11.5px;
    border-top: 1px solid #e3e6ea;
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
}
.diff-empty { padding: 20px; text-align: center; color: #6a7079; }
"""


def build_ui(
    *,
    mode: Mode,
    model: str,
    endpoint: str,
    voice_live_endpoint: str,
    shared: SharedState,
    handler,
    rtc_configuration: dict[str, Any] | None = None,
) -> gr.Blocks:
    with gr.Blocks(
        title="Voice Live Gradio Demo",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
            font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
        ),
        css=CUSTOM_CSS,
    ) as demo:
        gr.HTML(_header_html(mode, model, endpoint))

        with gr.Tabs():
            with gr.Tab("Talk"):
                with gr.Row(equal_height=False):
                    # Left: mic + transcript stacked
                    with gr.Column(scale=3):
                        with gr.Row(equal_height=True):
                            with gr.Column(scale=10, min_width=0):
                                gr.HTML('<div class="vl-section-title">Microphone</div>')
                            with gr.Column(scale=2, min_width=120, elem_classes="vl-status-cell"):
                                status_html = gr.HTML(_status_html("idle"))
                        with gr.Group(elem_classes="vl-mic-group"):
                            webrtc = WebRTC(
                                label="",
                                modality="audio",
                                mode="send-receive",
                                rtc_configuration=rtc_configuration,
                                icon_button_color="#0078D4",
                                pulse_color="#d63384",
                                full_screen=False,
                            )
                        gr.HTML('<div class="vl-section-title" style="margin-top:18px;">Transcript</div>')
                        chatbot = gr.Chatbot(
                            type="messages",
                            label="",
                            height=420,
                            show_copy_button=True,
                            show_label=False,
                            placeholder="<div style='color:#9aa0a7;font-style:italic;text-align:center;padding:24px;'>Conversation will appear here once you start talking.</div>",
                            avatar_images=(None, "https://learn.microsoft.com/favicon.ico"),
                        )

                    # Right: settings sidebar
                    with gr.Column(scale=1, min_width=300):
                        gr.HTML('<div class="vl-section-title">Settings</div>')
                        with gr.Group():
                            voice = gr.Dropdown(
                                choices=VOICE_OPTIONS,
                                value=shared.voice,
                                label="Voice",
                                interactive=True,
                            )
                            instructions = gr.Textbox(
                                value=shared.instructions,
                                label="System instructions",
                                lines=6,
                                max_lines=10,
                                interactive=True,
                            )
                        with gr.Row(elem_classes="vl-button-row"):
                            apply_btn = gr.Button("Apply", variant="primary", size="sm", scale=1)
                            reset_btn = gr.Button("Reset", variant="secondary", size="sm", scale=1)
                        gr.HTML('<div class="vl-section-title" style="margin-top:18px;">Connection</div>')
                        with gr.Group():
                            session_info = gr.Markdown(value="_No active session._")
                            with gr.Accordion("Backend details", open=False):
                                gr.Markdown(
                                    f"**Foundry endpoint**\n\n`{endpoint}`\n\n"
                                    f"**Voice Live WSS**\n\n`{voice_live_endpoint}`\n\n"
                                    f"**Mode** · `{mode.value}`\n\n"
                                    f"**Auth** · `DefaultAzureCredential` (Entra ID, no API keys)"
                                )

                webrtc.stream(
                    fn=handler,
                    inputs=[webrtc],
                    outputs=[webrtc],
                )
                webrtc.on_additional_outputs(
                    fn=_bind_state_outputs,
                    inputs=[chatbot, status_html, session_info],
                    outputs=[chatbot, status_html, session_info],
                )

                def _apply_settings(v: str, ins: str) -> str:
                    shared.voice = v
                    shared.instructions = ins
                    return _status_html("idle")

                apply_btn.click(
                    fn=_apply_settings,
                    inputs=[voice, instructions],
                    outputs=[status_html],
                )

                def _reset_conversation() -> tuple[list, str]:
                    shared.reset_requested = True
                    return [], _status_html("idle")

                reset_btn.click(fn=_reset_conversation, inputs=None, outputs=[chatbot, status_html])

            with gr.Tab("Switch diff"):
                gr.Markdown(
                    """
### How trivial is the switch?

Three sibling app files at the repo root, one per rung. The shared
plumbing (UI, FastRTC pipe, audio queue, transcript fan-out) lives in
`voicelive_demo/` — so what you see below is **the only thing that
changes per rung**.
                    """
                )
                gr.HTML(render_diffs_html())

            with gr.Tab("About"):
                gr.Markdown(
                    f"""
### About this demo

This repository started as a one-line proof that **Azure AI Foundry Voice
Live is a drop-in replacement for Azure OpenAI Realtime** — same SDK,
same call shape, just a different WebSocket destination.

The May 2026 refresh brings it forward to GA:

- **`openai` Python SDK** is on the GA `client.realtime.connect` path
  (`client.beta.realtime` was deprecated, sunset April 30, 2026).
- **Azure OpenAI Realtime** uses api-version `2025-04-01-preview`
  because the GA `/openai/v1/realtime` path isn't emitted by
  `openai 2.x` yet; will switch when it ships.
- **Azure Voice Live** is GA on api-version `2025-10-01`.
- **Default model**: `gpt-realtime-1.5` (2026-02-23) — the newest one
  Voice Live serves in Sweden Central as of May 2026.
- Bonus: `gpt-realtime-2` (2026-05-06) is deployed and usable from
  the Realtime rung; Voice Live's hosted menu hasn't picked it up yet.

### Current backend

| | |
|-|-|
| Mode | `{mode.value}` |
| Foundry endpoint | `{endpoint}` |
| Voice Live WSS | `{voice_live_endpoint}` |
| Model | `{model}` |
| Auth | Entra ID via `DefaultAzureCredential` |

### Switching modes

Set `MODE=` in `.env` and restart:

```
MODE=realtime    # Azure OpenAI Realtime (rung 1)
MODE=voicelive   # Azure Voice Live      (rung 2)  ← default
MODE=agent       # Voice Live + Foundry Agent (rung 3)
```
                    """
                )

    return demo
