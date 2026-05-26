"""Gradio Blocks UI for the demo.

This file is intentionally the *only* place where presentation lives. The three
`app_*.py` files at the repo root pass in their connection details and we
render a consistent, branded, info-rich UI on top.
"""
from __future__ import annotations

from typing import Any

import gradio as gr
from fastrtc import WebRTC

from voicelive_demo.config import Mode
from voicelive_demo.diff_assets import render_diffs_html
from voicelive_demo.handler import SharedState, StatusEvent

MODE_LABELS = {
    Mode.REALTIME:  ("rung 1 · Azure OpenAI Realtime",  "#0078D4"),  # Microsoft blue
    Mode.VOICELIVE: ("rung 2 · Azure Voice Live",       "#107C10"),  # Microsoft green
    Mode.AGENT:     ("rung 3 · Voice Live + Foundry Agent", "#7719AA"),  # purple
}

STATUS_PALETTE = {
    "idle":       ("Idle",          "#6c757d"),
    "connecting": ("Connecting…",   "#0d6efd"),
    "listening":  ("Listening 🎙️",  "#d63384"),
    "thinking":   ("Thinking…",     "#fd7e14"),
    "speaking":   ("Speaking 🔊",   "#198754"),
    "error":      ("Error ⚠️",      "#dc3545"),
}

# Short labels — the dropdown column is narrow and long labels get clipped.
VOICE_OPTIONS = [
    ("🟢 Ava (default)",  "en-US-Ava:DragonHDLatestNeural"),
    ("🟢 Jenny",          "en-US-Jenny:DragonHDLatestNeural"),
    ("🟢 Davis",          "en-US-Davis:DragonHDLatestNeural"),
    ("🟢 Guy",            "en-US-GuyNeural"),
    ("🟢 Brian",          "en-US-BrianNeural"),
    ("🔵 Alloy (OpenAI)", "alloy"),
    ("🔵 Nova (OpenAI)",  "nova"),
    ("🔵 Shimmer (OpenAI)", "shimmer"),
]


def _badge_html(label: str, value: str, color: str = "#0078D4") -> str:
    return (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:12px;'
        f'background:{color};color:white;font-weight:600;font-size:12.5px;'
        f'margin:2px 4px 2px 0;letter-spacing:.2px;">'
        f'<span style="opacity:.75;">{label}</span> · {value}</span>'
    )


def _header_html(mode: Mode, model: str, endpoint: str) -> str:
    mode_label, mode_color = MODE_LABELS[mode]
    short_endpoint = endpoint.replace("wss://", "").replace("https://", "").split("/")[0]
    badges = (
        _badge_html("MODE", mode_label, mode_color)
        + _badge_html("MODEL", model, "#444")
        + _badge_html("ENDPOINT", short_endpoint, "#888")
    )
    return f"""
<div style="padding:14px 18px;background:linear-gradient(180deg,#f8f9fa 0%,#f1f3f5 100%);
            border-radius:10px;margin-bottom:10px;border-left:5px solid {mode_color};">
  <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:6px;">
    <span style="font-size:22px;font-weight:700;color:#222;">🎙️ Voice Live Gradio Demo</span>
    <span style="font-size:13px;color:#666;">
      Drop-in switch · Azure OpenAI Realtime → Azure AI Foundry Voice Live
    </span>
  </div>
  <div style="line-height:2;">{badges}</div>
</div>
"""


def _status_html(status: str = "idle") -> str:
    label, color = STATUS_PALETTE.get(status, STATUS_PALETTE["idle"])
    return (
        f'<div style="display:inline-block;padding:6px 14px;border-radius:8px;'
        f'background:{color}22;color:{color};border:1.5px solid {color};'
        f'font-weight:600;font-size:14px;">● {label}</div>'
    )


def _bind_state_outputs(chatbot: list[dict], status_html_value: str, session_info: str,
                        event: StatusEvent) -> tuple[list[dict], str, str]:
    """FastRTC additional_outputs_handler: route a StatusEvent into the 3 Gradio components.

    FastRTC calls this as ``fn(*input_component_values, *additional_output_args)``.
    """
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
footer {visibility: hidden;}
.gradio-container {max-width: 1180px !important; margin: 0 auto !important;}

/* Force the WebRTC audio widget to stay inside its column.
   FastRTC's `.full-screen` class makes the wave escape the container; we
   neutralise it with explicit positioning. The `full_screen=False` kwarg
   removes the class, but we belt-and-brace here in case it sneaks back. */
.audio-container, .gradio-webrtc-waveContainer, .wave-container {
    position: relative !important;
    min-height: 220px;
}

/* Diff tables: predictable widths, more breathing room */
.diff_table { width: 100% !important; table-layout: fixed; }
.diff_table td:nth-child(1), .diff_table td:nth-child(4) { width: 36px; color:#999; }
.diff_table td:nth-child(2), .diff_table td:nth-child(5) { width: calc(50% - 60px); }

/* Tab bar — bigger, more clickable */
.tab-nav button { font-size: 15px !important; padding: 10px 16px !important; }
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
    """Assemble the Gradio Blocks UI around the FastRTC WebRTC component.

    Pass the ``VoiceHandler`` instance as ``handler``; FastRTC's ``WebRTC.stream(fn=handler)``
    accepts it directly and wires the audio pipe automatically.
    """
    with gr.Blocks(
        title="Voice Live Gradio Demo",
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="emerald"),
        css=CUSTOM_CSS,
    ) as demo:
        gr.HTML(_header_html(mode, model, endpoint))

        with gr.Tabs():
            with gr.Tab("🎙️ Talk"):
                # Row 1: mic widget (big) + live status (pinned right)
                with gr.Row(equal_height=False):
                    with gr.Column(scale=4):
                        with gr.Group():
                            webrtc = WebRTC(
                                label="🎤 Microphone — click ⏺ Record to start talking",
                                modality="audio",
                                mode="send-receive",
                                rtc_configuration=rtc_configuration,
                                icon_button_color="#107C10",
                                pulse_color="#d63384",
                                full_screen=False,
                            )
                    with gr.Column(scale=1, min_width=200):
                        status_html = gr.HTML(_status_html("idle"))
                        gr.Markdown(
                            "💡 _Click **⏺ Record**, then talk. "
                            "The assistant interrupts naturally._"
                        )

                # Row 2: transcript (left, wide) + controls (right, compact)
                with gr.Row(equal_height=False):
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(
                            type="messages",
                            label="Transcript",
                            height=460,
                            show_copy_button=True,
                            avatar_images=(None, "https://learn.microsoft.com/favicon.ico"),
                        )
                    with gr.Column(scale=1, min_width=280):
                        voice = gr.Dropdown(
                            choices=VOICE_OPTIONS,
                            value=shared.voice,
                            label="Voice",
                            info="🟢 Azure Neural · 🔵 OpenAI · applies on next session",
                            interactive=True,
                        )
                        instructions = gr.Textbox(
                            value=shared.instructions,
                            label="System instructions",
                            lines=5,
                            max_lines=8,
                            interactive=True,
                        )
                        with gr.Row():
                            apply_btn = gr.Button("Apply ↻", variant="primary", size="sm")
                            reset_btn = gr.Button("Reset 🗑️", variant="secondary", size="sm")
                        with gr.Accordion("Connection details", open=False):
                            session_info = gr.Markdown(value="_No session yet._")
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

            with gr.Tab("🧩 View the diff"):
                gr.Markdown(
                    """
### How trivial is the switch?

Three sibling app files; each is a tiny diff from the previous one. The
plumbing (Gradio UI, FastRTC pipe, audio queue, transcript fan-out) lives in
`voicelive_demo/` and is shared by all three — so the diffs you see below are
**the only thing that changes per rung**.
                    """
                )
                gr.HTML(render_diffs_html())

            with gr.Tab("ℹ️ About"):
                gr.Markdown(
                    f"""
### About this demo

This repository started as a one-line proof that **Azure AI Foundry Voice
Live is a drop-in replacement for Azure OpenAI Realtime** — same SDK, same
call shape, just a different WebSocket destination.

This refresh (May 2026) brings it forward to GA:

- **`openai` Python SDK** is on the GA `client.realtime.connect` path
  (`client.beta.realtime` is deprecated, sunset April 30, 2026).
- **Azure OpenAI Realtime** uses api-version `2025-04-01-preview`
  because the GA `/openai/v1/realtime` path isn't emitted by `openai 2.x`
  yet; will switch when it ships.
- **Azure Voice Live** is GA on api-version `2025-10-01`.
- **Default model**: `gpt-realtime-1.5` (2026-02-23) — the newest one
  Voice Live serves in Sweden Central as of May 2026.
- Bonus: `gpt-realtime-2` (2026-05-06) is also deployed and usable from
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
