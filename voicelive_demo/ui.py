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
/* ── Theme tokens ──────────────────────────────────────────────────── */
:root {
    --vl-bg:              #f5f6f8;
    --vl-surface:         #ffffff;
    --vl-surface-soft:    #fafbfc;
    --vl-border:          #e3e6ea;
    --vl-border-strong:   #d8dde3;
    --vl-text:            #1a1a1a;
    --vl-text-muted:      #5a6068;
    --vl-text-faint:      #6a7079;
    --vl-text-placeholder:#9aa0a7;
    --vl-accent:          #0078D4;
    --vl-accent-hover:    #106ebe;
    --vl-accent-ring:     rgba(0,120,212,0.18);
    --vl-shadow:          0 1px 2px rgba(0,0,0,0.04);
    --vl-mono:            "SF Mono","Cascadia Mono",Consolas,Menlo,monospace;

    --vl-diff-row-border: #f0f2f5;
    --vl-diff-lno-bg:     #fafbfc;
    --vl-diff-lno-text:   #9aa0a7;
    --vl-diff-header-bg:  #f6f8fa;
    --vl-diff-hunk-bg:    #f1f3f6;
    --vl-diff-add-bg:     #e6ffec;
    --vl-diff-del-bg:     #ffeef0;
    --vl-diff-add-sign-bg:#ccffd8;
    --vl-diff-del-sign-bg:#ffd8d3;
    --vl-diff-add-sign-tx:#1a7f37;
    --vl-diff-del-sign-tx:#cf222e;
    --vl-diff-code-tx:    #1a1a1a;
}

/* Gradio sets `.dark` on <gradio-app> / <body> when OS / user picks dark. */
.dark, body.dark, gradio-app.dark, .gradio-container.dark {
    --vl-bg:              #0d1117;
    --vl-surface:         #161b22;
    --vl-surface-soft:    #1c2128;
    --vl-border:          #30363d;
    --vl-border-strong:   #3d444d;
    --vl-text:            #e6edf3;
    --vl-text-muted:      #b1bac4;
    --vl-text-faint:      #8b949e;
    --vl-text-placeholder:#6e7681;
    --vl-accent:          #58a6ff;
    --vl-accent-hover:    #79b8ff;
    --vl-accent-ring:     rgba(88,166,255,0.25);
    --vl-shadow:          0 1px 2px rgba(0,0,0,0.5);

    --vl-diff-row-border: #21262d;
    --vl-diff-lno-bg:     #0d1117;
    --vl-diff-lno-text:   #6e7681;
    --vl-diff-header-bg:  #161b22;
    --vl-diff-hunk-bg:    #1c2128;
    --vl-diff-add-bg:     rgba(46,160,67,0.18);
    --vl-diff-del-bg:     rgba(248,81,73,0.18);
    --vl-diff-add-sign-bg:rgba(46,160,67,0.40);
    --vl-diff-del-sign-bg:rgba(248,81,73,0.40);
    --vl-diff-add-sign-tx:#7ee787;
    --vl-diff-del-sign-tx:#ff7b72;
    --vl-diff-code-tx:    #e6edf3;
}

/* ── Reset & globals ───────────────────────────────────────────────── */
footer {display:none !important;}
.gradio-container {
    max-width: 1200px !important;
    margin: 0 auto !important;
    padding: 24px 28px 48px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", system-ui, sans-serif !important;
    background: var(--vl-bg) !important;
    color: var(--vl-text) !important;
}
.gradio-container, .gradio-container * { box-sizing: border-box; }
body, gradio-app { background: var(--vl-bg) !important; color: var(--vl-text) !important; }

/* ── Header ────────────────────────────────────────────────────────── */
.vl-header {
    background: var(--vl-surface);
    border: 1px solid var(--vl-border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 18px;
    display: flex; flex-direction: column; gap: 16px;
    box-shadow: var(--vl-shadow);
}
.vl-header-main { display: flex; flex-direction: column; gap: 4px; }
.vl-title {
    font-size: 22px; font-weight: 600;
    color: var(--vl-text);
    letter-spacing: -0.01em; line-height: 1.2;
}
.vl-title-thin { font-weight: 400; color: var(--vl-text-muted); }
.vl-subtitle { font-size: 14px; color: var(--vl-text-muted); line-height: 1.4; }

.vl-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.vl-chip {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 12px;
    border: 1px solid var(--vl-border);
    background: var(--vl-surface-soft);
    border-radius: 8px;
    font-size: 12.5px;
}
.vl-chip-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.vl-chip-label {
    color: var(--vl-text-faint); font-weight: 600; letter-spacing: 0.06em; font-size: 11px;
    text-transform: uppercase;
}
.vl-chip-value { color: var(--vl-text); font-weight: 500; }
.vl-mono { font-family: var(--vl-mono); font-size: 12px; }

/* ── Tabs ──────────────────────────────────────────────────────────── */
.tab-nav { border-bottom: 1px solid var(--vl-border) !important; margin-bottom: 18px !important; }
.tab-nav button {
    font-size: 14px !important; font-weight: 500 !important;
    padding: 12px 18px !important;
    color: var(--vl-text-muted) !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    transition: color 0.15s ease, border-color 0.15s ease;
}
.tab-nav button.selected {
    color: var(--vl-accent) !important;
    border-bottom-color: var(--vl-accent) !important;
}
.tab-nav button:hover:not(.selected) { color: var(--vl-text) !important; }

/* ── Cards (Gradio groups) ─────────────────────────────────────────── */
.gr-group, .gradio-container .form, fieldset {
    background: var(--vl-surface) !important;
    border: 1px solid var(--vl-border) !important;
    border-radius: 10px !important;
    box-shadow: var(--vl-shadow) !important;
}

/* Kill Gradio Soft-theme's rounded label pills. Gradio uses two different
   testids for label-style elements:
     - label[data-testid="block-label"]  (chatbot, audio, image, …)
     - span[data-testid="block-info"]    (textbox, dropdown, …)
*/
.gradio-container label[data-testid="block-label"],
.gradio-container label[data-testid="block-label"] > span,
.gradio-container span[data-testid="block-info"] {
    background: transparent !important;
    color: var(--vl-text) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 0 0 6px 0 !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}
.gradio-container label[data-testid="block-label"] > span { padding: 0 !important; }
.gradio-container span[data-testid="block-info"] { display: block; margin-bottom: 4px; }
.gradio-container label[data-testid="block-label"] svg { display: none !important; }

/* Hide the WebRTC widget's own "Audio" label — the section heading above
   it already says "Microphone". */
.vl-mic-group label[data-testid="block-label"] { display: none !important; }

/* Inputs & textareas */
.gradio-container input[type="text"],
.gradio-container textarea,
.gradio-container input[type="search"],
.gradio-container .gr-input {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
    border: 1px solid var(--vl-border-strong) !important;
    border-radius: 8px !important;
    font-size: 14px !important;
}
.gradio-container input::placeholder,
.gradio-container textarea::placeholder { color: var(--vl-text-placeholder) !important; }
.gradio-container input[type="text"]:focus,
.gradio-container input[type="search"]:focus,
.gradio-container textarea:focus {
    border-color: var(--vl-accent) !important;
    box-shadow: 0 0 0 3px var(--vl-accent-ring) !important;
    outline: none !important;
}

/* Dropdown */
.gradio-container .wrap-inner { background: var(--vl-surface) !important; color: var(--vl-text) !important; }
.gradio-container ul[role="listbox"] {
    background: var(--vl-surface) !important; color: var(--vl-text) !important;
    border: 1px solid var(--vl-border-strong) !important;
}
.gradio-container ul[role="listbox"] li:hover {
    background: var(--vl-surface-soft) !important; color: var(--vl-text) !important;
}

/* Buttons */
.gradio-container button.primary, .gradio-container button[class*="primary"] {
    background: var(--vl-accent) !important;
    border-color: var(--vl-accent) !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}
.gradio-container button.primary:hover { background: var(--vl-accent-hover) !important; }
.gradio-container button.secondary, .gradio-container button[class*="secondary"] {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
    border: 1px solid var(--vl-border-strong) !important;
    border-radius: 8px !important;
}
.gradio-container button.secondary:hover { background: var(--vl-surface-soft) !important; }

/* Accordion */
.gradio-container .label-wrap, .gradio-container .open > .label-wrap {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
    border-radius: 8px !important;
}

/* Chatbot */
.gradio-container .chatbot, .gradio-container [data-testid="chatbot"] {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
}
.gradio-container .placeholder {
    color: var(--vl-text-placeholder) !important;
    font-style: italic;
}

/* Markdown (About tab, etc) */
.gradio-container .prose, .gradio-container .markdown { color: var(--vl-text) !important; }
.gradio-container .prose h1, .gradio-container .prose h2,
.gradio-container .prose h3, .gradio-container .prose h4 { color: var(--vl-text) !important; }
.gradio-container .prose code, .gradio-container code:not([class]) {
    background: var(--vl-surface-soft) !important;
    color: var(--vl-text) !important;
    border: 1px solid var(--vl-border) !important;
    padding: 1px 6px !important;
    border-radius: 4px !important;
    font-family: var(--vl-mono) !important;
    font-size: 0.9em !important;
}
.gradio-container .prose pre {
    background: var(--vl-surface-soft) !important;
    color: var(--vl-text) !important;
    border: 1px solid var(--vl-border) !important;
}
.gradio-container .prose table {
    background: var(--vl-surface) !important;
    border-color: var(--vl-border) !important;
}
.gradio-container .prose th, .gradio-container .prose td {
    border-color: var(--vl-border) !important;
    color: var(--vl-text) !important;
}
.gradio-container .prose th { background: var(--vl-surface-soft) !important; }

/* ── Status pill ───────────────────────────────────────────────────── */
.vl-status {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 12px; border-radius: 999px;
    background: color-mix(in srgb, var(--status) 14%, transparent);
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
    color: var(--vl-text-faint);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0 0 8px 0;
}
.vl-status-cell { display: flex !important; justify-content: flex-end !important; align-items: center !important; }
.vl-status-cell > div { display: inline-flex; }

/* Side-by-side action buttons */
.vl-button-row { gap: 8px !important; margin-top: 8px !important; }
.vl-button-row > button, .vl-button-row .gr-button { flex: 1 !important; min-width: 0 !important; }

/* ── Switch-diff (minimal view) ────────────────────────────────────── */
.vlx-root { display: flex; flex-direction: column; gap: 28px; }

.vlx-section {
    background: var(--vl-surface);
    border: 1px solid var(--vl-border);
    border-radius: 12px;
    padding: 20px 22px 22px;
    box-shadow: var(--vl-shadow);
}

.vlx-section-head {
    display: flex; align-items: center; gap: 12px;
    margin: 0 0 6px 0;
}
.vlx-step {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; border-radius: 50%;
    background: var(--vl-accent); color: #fff;
    font-size: 13px; font-weight: 700;
    flex: 0 0 auto;
}
.vlx-section-title {
    font-size: 16px; font-weight: 600; color: var(--vl-text);
    letter-spacing: -0.005em;
}
.vlx-lede {
    color: var(--vl-text-muted); font-size: 13.5px; line-height: 1.55;
    margin: 0 0 14px 0;
}
.vlx-lede code {
    background: var(--vl-surface-soft); padding: 1px 6px; border-radius: 4px;
    font-family: var(--vl-mono); font-size: 12.5px;
    color: var(--vl-text);
    border: 1px solid var(--vl-border);
}

.vlx-summary {
    display: flex; flex-wrap: wrap; gap: 6px;
    margin: 0 0 14px 0;
}
.vlx-summary-chip {
    display: inline-flex; align-items: center;
    padding: 3px 10px;
    border-radius: 999px;
    border: 1px solid var(--vl-border);
    background: var(--vl-surface-soft);
    color: var(--vl-text-muted);
    font-size: 12px; font-weight: 600;
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
}
.vlx-summary-chip-add {
    color: var(--vl-diff-add-sign-tx);
    background: var(--vl-diff-add-bg);
    border-color: color-mix(in srgb, var(--vl-diff-add-sign-tx) 30%, transparent);
}
.vlx-summary-chip-del {
    color: var(--vl-diff-del-sign-tx);
    background: var(--vl-diff-del-bg);
    border-color: color-mix(in srgb, var(--vl-diff-del-sign-tx) 30%, transparent);
}
.vlx-summary-chip-info {
    color: var(--vl-accent);
    background: color-mix(in srgb, var(--vl-accent) 8%, transparent);
    border-color: color-mix(in srgb, var(--vl-accent) 25%, transparent);
}

.vlx-panel {
    border: 1px solid var(--vl-border-strong);
    border-radius: 8px;
    overflow: hidden;
    background: var(--vl-surface);
    margin-top: 10px;
}
.vlx-panel + .vlx-panel { margin-top: 14px; }
.vlx-panel-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px;
    padding: 8px 14px;
    background: var(--vl-diff-header-bg);
    border-bottom: 1px solid var(--vl-border-strong);
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
}
.vlx-fn {
    font-family: var(--vl-mono);
    font-size: 12.5px;
    color: var(--vl-text);
    font-weight: 600;
    background: transparent;
    padding: 0;
}
.vlx-stats { display: inline-flex; gap: 6px; }
.vlx-chip {
    display: inline-flex; align-items: center;
    padding: 1px 8px;
    border-radius: 4px;
    font-family: var(--vl-mono);
    font-size: 11.5px; font-weight: 700;
    line-height: 1.5;
}
.vlx-chip-add {
    color: var(--vl-diff-add-sign-tx);
    background: var(--vl-diff-add-sign-bg);
}
.vlx-chip-del {
    color: var(--vl-diff-del-sign-tx);
    background: var(--vl-diff-del-sign-bg);
}

.vlx-diff {
    font-family: var(--vl-mono);
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--vl-diff-code-tx);
    background: var(--vl-surface);
    overflow-x: auto;
}
.vlx-row {
    display: grid;
    grid-template-columns: 44px 44px 24px 1fr;
    align-items: stretch;
    min-height: 22px;
}
.vlx-lno {
    padding: 0 8px; text-align: right;
    color: var(--vl-diff-lno-text); user-select: none;
    background: var(--vl-diff-lno-bg);
    font-size: 11.5px;
    border-right: 1px solid var(--vl-diff-row-border);
    display: flex; align-items: center; justify-content: flex-end;
}
.vlx-sign {
    padding: 0; text-align: center;
    color: var(--vl-text-muted); user-select: none;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
}
.vlx-code {
    padding: 0 12px;
    white-space: pre;
    color: var(--vl-diff-code-tx);
    display: flex; align-items: center;
}
.vlx-ctx > .vlx-code,
.vlx-ctx > .vlx-sign { background: var(--vl-surface); }
.vlx-add > .vlx-code { background: var(--vl-diff-add-bg); }
.vlx-add > .vlx-sign { background: var(--vl-diff-add-sign-bg); color: var(--vl-diff-add-sign-tx); }
.vlx-del > .vlx-code { background: var(--vl-diff-del-bg); }
.vlx-del > .vlx-sign { background: var(--vl-diff-del-sign-bg); color: var(--vl-diff-del-sign-tx); }

.vlx-gap {
    grid-template-columns: 1fr;
    min-height: 8px;
    background: var(--vl-diff-hunk-bg);
    border-top: 1px solid var(--vl-diff-row-border);
    border-bottom: 1px solid var(--vl-diff-row-border);
}
.vlx-gap .vlx-spacer { display: block; }

.vlx-diff-empty {
    padding: 20px; text-align: center;
    color: var(--vl-text-faint);
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}
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
                gr.HTML(
                    '<div class="vl-section-title" style="margin:8px 0 4px;">How trivial is the switch?</div>'
                    '<p style="margin:0 0 16px 0;color:var(--vl-text-muted);font-size:13.5px;line-height:1.55;">'
                    "Three sibling app files at the repo root, one per rung. "
                    "All shared plumbing (UI, FastRTC pipe, audio queue, transcript fan-out) "
                    "lives in <code style=\"font-family:var(--vl-mono);background:var(--vl-surface-soft);"
                    "padding:1px 6px;border-radius:4px;border:1px solid var(--vl-border);font-size:12.5px;\">"
                    "voicelive_demo/</code>. Below is the entire delta — only the functions "
                    "that actually change between rungs."
                    "</p>"
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
