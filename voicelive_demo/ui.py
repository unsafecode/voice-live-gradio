"""Gradio Blocks UI for the demo.

The single place where presentation lives. The four `app_*.py` shells at
the repo root pass in the rung registry + settings; this module renders a
consistent, branded UI on top, and optionally a runtime mode switcher
when more than one rung is registered.
"""
from __future__ import annotations

from typing import Any

import gradio as gr
from fastrtc import WebRTC

from voicelive_demo.config import Mode, Settings
from voicelive_demo.diff_assets import render_diffs_html
from voicelive_demo.handler import SharedState, StatusEvent
from voicelive_demo.i18n import (
    DEFAULT_INSTRUCTIONS,
    DEFAULT_VOICE,
    LOCALES,
    RUNG_BLURBS,
    STATUS_LABELS,
    STRINGS,
    VOICE_OPTIONS,
)
from voicelive_demo.rungs import REGISTRY, Rung

STATUS_COLORS = {
    "idle":       "#6c757d",
    "connecting": "#0d6efd",
    "listening":  "#d63384",
    "thinking":   "#fd7e14",
    "speaking":   "#198754",
    "error":      "#dc3545",
}

VOICE_OPTIONS_FOR = VOICE_OPTIONS  # re-export for readability


def _voice_choices(locale: str) -> list[tuple[str, str]]:
    """The voice picker shows (label, voice-name) pairs — locale-aware."""
    return [(label, name) for (label, name, _vtype) in VOICE_OPTIONS[locale]]


def _voice_type_lookup(locale: str) -> dict[str, str]:
    """voice_name → voice_type so the rung can set the right session field."""
    return {name: vtype for (_label, name, vtype) in VOICE_OPTIONS[locale]}


def _short_endpoint(endpoint: str) -> str:
    return endpoint.replace("wss://", "").replace("https://", "").split("/")[0]


def _destination_html(rung: Rung, settings: Settings, t: dict[str, str]) -> str:
    """Render the 'where you're landing' line for the active rung — model + endpoint."""
    endpoint = (
        settings.azure_voice_live_endpoint if rung.mode in (Mode.VOICELIVE, Mode.AGENT)
        else settings.azure_endpoint
    )
    return f"""
<div class="vl-dest" style="--rung-color:{rung.color};">
  <span class="vl-dest-arrow">→</span>
  <span class="vl-dest-rung">{rung.label}</span>
  <span class="vl-dest-sep">·</span>
  <span class="vl-dest-key">model</span>
  <span class="vl-dest-val vl-mono">{settings.azure_deployment_name}</span>
  <span class="vl-dest-sep">·</span>
  <span class="vl-dest-key">endpoint</span>
  <span class="vl-dest-val vl-mono">{_short_endpoint(endpoint)}</span>
</div>
"""


def _hero_main_html(t: dict[str, str]) -> str:
    return f"""
<div class="vl-hero-main">
  <div class="vl-hero-eyebrow">{t['eyebrow']}</div>
  <div class="vl-title">Voice Live <span class="vl-title-thin">Gradio Demo</span></div>
  <div class="vl-subtitle">{t['subtitle']}</div>
</div>
"""


def _status_html(status: str = "idle", locale: str = "en") -> str:
    label = STATUS_LABELS.get(locale, STATUS_LABELS["en"]).get(status, STATUS_LABELS["en"]["idle"])
    color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
    return (
        f'<div class="vl-status" style="--status:{color};">'
        f'<span class="vl-status-dot"></span>'
        f'<span class="vl-status-label">{label}</span>'
        f'</div>'
    )


def _section_title_html(text: str, top: int = 0) -> str:
    style = f' style="margin-top:{top}px;"' if top else ""
    return f'<div class="vl-section-title"{style}>{text}</div>'


def _livemode_head_html(t: dict[str, str]) -> str:
    return (
        '<div class="vl-livemode-head">'
        f'<span class="vl-livemode-eyebrow">{t["live_mode"]}</span>'
        f'<span class="vl-livemode-hint">{t["live_hint"]}</span>'
        '</div>'
    )


def _blurb_html(rung: Rung, locale: str) -> str:
    blurb = RUNG_BLURBS.get(locale, RUNG_BLURBS["en"]).get(rung.mode.value, rung.blurb)
    return f'<div class="vl-mode-blurb">{blurb}</div>'


def _chatbot_placeholder_html(t: dict[str, str]) -> str:
    return (
        "<div style='color:#9aa0a7;font-style:italic;text-align:center;"
        f"padding:24px;'>{t['transcript_placeholder']}</div>"
    )


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

/* ── Hero (page header) ─────────────────────────────────────────────── */
.vl-hero {
    background: var(--vl-surface) !important;
    border: 1px solid var(--vl-border) !important;
    border-radius: 14px !important;
    padding: 0 !important;
    margin-bottom: 18px !important;
    overflow: hidden;
    box-shadow: var(--vl-shadow);
    position: relative;
}
.vl-hero-accent {
    height: 4px;
    background: linear-gradient(90deg, #0078D4 0%, #107C10 55%, #7719AA 100%);
}
.vl-hero-body { padding: 18px 26px 20px !important; gap: 18px !important; align-items: flex-start !important; }
.vl-hero-main { display: flex; flex-direction: column; gap: 6px; }
.vl-hero-eyebrow {
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--vl-text-faint);
}
.vl-title {
    font-size: 24px; font-weight: 700;
    color: var(--vl-text);
    letter-spacing: -0.015em; line-height: 1.15;
}
.vl-title-thin { font-weight: 400; color: var(--vl-text-muted); }
.vl-subtitle { font-size: 14px; color: var(--vl-text-muted); line-height: 1.5; max-width: 760px; }
.vl-mono { font-family: var(--vl-mono); font-size: 12px; }

/* Language switcher (in hero, top-right) */
.vl-hero-side {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-end !important;
    gap: 6px !important;
}
.vl-lang-label {
    font-size: 10.5px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--vl-text-faint);
    text-align: right;
}
.vl-lang-switcher {
    display: inline-flex !important;
    flex-wrap: nowrap !important;
    gap: 0 !important;
    padding: 3px !important;
    background: var(--vl-surface-soft) !important;
    border: 1px solid var(--vl-border) !important;
    border-radius: 8px !important;
    width: fit-content !important;
}
.vl-lang-switcher .gr-button,
.vl-lang-switcher button.vl-lang-btn {
    flex: 0 0 auto !important;
    min-width: 0 !important;
    padding: 5px 12px !important;
    margin: 0 !important;
    border-radius: 5px !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    border: none !important;
    box-shadow: none !important;
    transition: background 0.15s ease, color 0.15s ease;
}
.vl-lang-switcher button.vl-lang-idle {
    background: transparent !important;
    color: var(--vl-text-muted) !important;
}
.vl-lang-switcher button.vl-lang-idle:hover {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
}
.vl-lang-switcher button.vl-lang-active {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08), 0 0 0 1px var(--vl-border-strong) !important;
}

/* ── Live mode card (inside Talk tab) ───────────────────────────────── */
.vl-livemode {
    background: var(--vl-surface) !important;
    border: 1px solid var(--vl-border) !important;
    border-radius: 12px !important;
    padding: 16px 18px !important;
    margin-bottom: 16px !important;
    box-shadow: var(--vl-shadow);
    display: flex !important;
    flex-direction: column !important;
    gap: 10px !important;
}
.vl-livemode-head {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 16px; flex-wrap: wrap;
}
.vl-livemode-eyebrow {
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--vl-text-faint);
}
.vl-livemode-hint {
    font-size: 12.5px; color: var(--vl-text-muted);
    font-style: italic;
}
.vl-livemode-body {
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
}

/* Segmented switcher */
.vl-switcher {
    display: inline-flex !important;
    flex-wrap: nowrap !important;
    gap: 0 !important;
    padding: 4px !important;
    background: var(--vl-surface-soft) !important;
    border: 1px solid var(--vl-border) !important;
    border-radius: 10px !important;
    width: fit-content !important;
    align-self: flex-start;
}
.vl-switcher .gr-button,
.vl-switcher button.vl-switcher-btn {
    flex: 0 0 auto !important;
    min-width: 0 !important;
    padding: 7px 14px 7px 30px !important;
    margin: 0 !important;
    border-radius: 7px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    border: none !important;
    box-shadow: none !important;
    transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
    position: relative !important;
}
/* Colored dot per rung — drawn via ::before so each pill is self-coloured. */
.vl-switcher button.vl-switcher-btn::before {
    content: "";
    position: absolute;
    left: 14px; top: 50%; transform: translateY(-50%);
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--vl-text-faint);
    transition: background 0.15s ease, box-shadow 0.15s ease;
}
.vl-switcher button.vl-switcher-realtime::before  { background: #0078D4; }
.vl-switcher button.vl-switcher-voicelive::before { background: #107C10; }
.vl-switcher button.vl-switcher-agent::before     { background: #7719AA; }

.vl-switcher button.vl-switcher-idle {
    background: transparent !important;
    color: var(--vl-text-muted) !important;
}
.vl-switcher button.vl-switcher-idle::before { opacity: 0.55; }
.vl-switcher button.vl-switcher-idle:hover {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
}
.vl-switcher button.vl-switcher-idle:hover::before { opacity: 1; }
.vl-switcher button.vl-switcher-active {
    background: var(--vl-surface) !important;
    color: var(--vl-text) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.10), 0 0 0 1px var(--vl-border-strong) !important;
}
.vl-switcher button.vl-switcher-realtime.vl-switcher-active::before  { box-shadow: 0 0 0 3px rgba(0,120,212,0.18); }
.vl-switcher button.vl-switcher-voicelive.vl-switcher-active::before { box-shadow: 0 0 0 3px rgba(16,124,16,0.18); }
.vl-switcher button.vl-switcher-agent.vl-switcher-active::before     { box-shadow: 0 0 0 3px rgba(119,25,170,0.18); }
.dark .vl-switcher button.vl-switcher-active {
    box-shadow: 0 1px 3px rgba(0,0,0,0.5), 0 0 0 1px var(--vl-border-strong) !important;
}

/* Single-rung badge (when len(rungs) == 1 — replaces the pill row) */
.vl-livemode-single {
    display: inline-flex; align-items: center; gap: 10px;
    padding: 8px 14px;
    background: var(--vl-surface-soft);
    border: 1px solid var(--vl-border);
    border-radius: 10px;
    font-size: 13.5px; font-weight: 600; color: var(--vl-text);
}
.vl-livemode-single .vl-dot {
    width: 10px; height: 10px; border-radius: 50%;
}

/* Destination line (key/value, mono) */
.vl-dest {
    display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap;
    padding: 8px 14px;
    background: var(--vl-surface-soft);
    border: 1px solid var(--vl-border);
    border-left: 3px solid var(--rung-color, var(--vl-accent));
    border-radius: 8px;
    font-size: 12.5px;
    color: var(--vl-text-muted);
    flex: 1 1 320px;
    min-width: 0;
}
.vl-dest-arrow { color: var(--rung-color, var(--vl-accent)); font-weight: 700; }
.vl-dest-rung  { color: var(--vl-text); font-weight: 600; }
.vl-dest-sep   { color: var(--vl-text-placeholder); }
.vl-dest-key   { color: var(--vl-text-faint); font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.vl-dest-val   { color: var(--vl-text); font-weight: 500; }

.vl-mode-blurb {
    color: var(--vl-text-muted);
    font-size: 13px;
    line-height: 1.5;
    margin: 0;
    padding-left: 2px;
}

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

/* Voice picker — keep long labels like "Isabella — Azure Multilingual (default)" inside the box */
.vl-voice-picker .secondary-wrap input,
.vl-voice-picker .wrap-inner input,
.vl-voice-picker input.border-none,
.vl-voice-picker input[type="text"] {
    text-overflow: ellipsis !important;
    overflow: hidden !important;
    padding-right: 32px !important;
}
.vl-voice-picker ul, .vl-voice-picker .options { max-width: 100% !important; }
.vl-voice-picker .item, .vl-voice-picker li {
    white-space: nowrap !important;
    text-overflow: ellipsis !important;
    overflow: hidden !important;
}

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
    rungs: list[Rung],
    initial_mode: Mode,
    settings: Settings,
    shared: SharedState,
    handler,
    rtc_configuration: dict[str, Any] | None = None,
) -> gr.Blocks:
    if not rungs:
        raise ValueError("build_ui requires at least one rung")
    rung_by_mode: dict[Mode, Rung] = {r.mode: r for r in rungs}
    initial_rung = rung_by_mode.get(initial_mode) or rungs[0]
    multi_rung = len(rungs) > 1

    initial_locale = shared.locale
    t = STRINGS[initial_locale]

    # Sync defaults to the locale's voice + instructions.
    default_voice_name, default_voice_type = DEFAULT_VOICE[initial_locale]
    shared.voice = default_voice_name
    shared.voice_type = default_voice_type
    shared.instructions = DEFAULT_INSTRUCTIONS[initial_locale]

    def _backend_md(t: dict[str, str]) -> str:
        return (
            f"**{t['foundry_endpoint']}**\n\n`{settings.azure_endpoint}`\n\n"
            f"**{t['voicelive_wss']}**\n\n`{settings.azure_voice_live_endpoint}`\n\n"
            f"**{t['default_model']}** · `{settings.azure_deployment_name}`\n\n"
            f"**{t['auth']}** · `DefaultAzureCredential` (Entra ID, no API keys)"
        )

    def _about_md(t: dict[str, str]) -> str:
        if initial_locale == "it":
            # Italian about copy — same content, translated.
            return f"""
### Informazioni sulla demo

Questo repository è nato come una prova in una sola riga del fatto che
**Azure AI Foundry Voice Live è un sostituto drop-in di Azure OpenAI
Realtime** — stesso SDK, stessa chiamata, solo una destinazione
WebSocket diversa.

L'aggiornamento di maggio 2026 lo porta in GA:

- **SDK Python `openai`** sul percorso GA `client.realtime.connect`
  (`client.beta.realtime` è stato deprecato, ritiro 30 aprile 2026).
- **Azure OpenAI Realtime** usa api-version `2025-04-01-preview` perché
  il path GA `/openai/v1/realtime` non è ancora esposto da `openai 2.x`;
  passeremo non appena disponibile.
- **Azure Voice Live** è GA su api-version `2025-10-01`.
- **Modello predefinito**: `gpt-realtime-1.5` (2026-02-23) — il più
  recente che Voice Live serve in Sweden Central a maggio 2026.

### Punti d'ingresso

| Comando | UI |
|---------|-----|
| `python app.py` (no MODE) | Switcher unificato — tutti i gradini disponibili |
| `MODE=realtime python app.py` | Solo Realtime |
| `MODE=voicelive python app.py` | Solo Voice Live |
| `MODE=agent python app.py` | Solo Voice Live + Foundry Agent (richiede `AGENT_ID`) |

### Backend corrente

| | |
|-|-|
| Gradini disponibili | `{', '.join(r.mode.value for r in rungs)}` |
| Endpoint Foundry | `{settings.azure_endpoint}` |
| WSS Voice Live | `{settings.azure_voice_live_endpoint}` |
| Modello | `{settings.azure_deployment_name}` |
| Autenticazione | Entra ID via `DefaultAzureCredential` |
"""
        return f"""
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

### Entry points

| Command | UI |
|---------|-----|
| `python app.py` (no MODE) | Unified switcher — all available rungs |
| `MODE=realtime python app.py` | Realtime only |
| `MODE=voicelive python app.py` | Voice Live only |
| `MODE=agent python app.py` | Voice Live + Foundry Agent only (requires `AGENT_ID`) |

### Current backend

| | |
|-|-|
| Available rungs | `{', '.join(r.mode.value for r in rungs)}` |
| Foundry endpoint | `{settings.azure_endpoint}` |
| Voice Live WSS | `{settings.azure_voice_live_endpoint}` |
| Model | `{settings.azure_deployment_name}` |
| Auth | Entra ID via `DefaultAzureCredential` |
"""

    def _diff_intro_html(t: dict[str, str]) -> str:
        return (
            f'<div class="vl-section-title" style="margin:8px 0 4px;">{t["diff_title"]}</div>'
            '<p style="margin:0 0 16px 0;color:var(--vl-text-muted);font-size:13.5px;line-height:1.55;">'
            f'{t["diff_lede"]}'
            '</p>'
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
            new_status = _status_html(event.payload["status"], shared.locale)
        elif event.kind == "session":
            sid = event.payload.get("session_id", "?")
            model = event.payload.get("model", "?")
            new_session = f"`session_id`: `{sid}`  ·  `model`: `{model}`"
        return new_chatbot, new_status, new_session

    with gr.Blocks(
        title="Voice Live Gradio Demo",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
            font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
        ),
        css=CUSTOM_CSS,
    ) as demo:
        # ── Hero (page-level header) ─────────────────────────────────
        lang_buttons: dict[str, gr.Button] = {}
        with gr.Group(elem_classes="vl-hero"):
            gr.HTML('<div class="vl-hero-accent"></div>')
            with gr.Row(elem_classes="vl-hero-body"):
                with gr.Column(scale=5, min_width=0):
                    hero_main_html = gr.HTML(_hero_main_html(t))
                with gr.Column(scale=0, min_width=200, elem_classes="vl-hero-side"):
                    lang_label_html = gr.HTML(
                        f'<div class="vl-lang-label">{t["language"]}</div>'
                    )
                    with gr.Row(elem_classes="vl-lang-switcher"):
                        for label, code in LOCALES:
                            is_active = (code == initial_locale)
                            lang_btn = gr.Button(
                                value=label,
                                size="sm",
                                elem_classes=[
                                    "vl-lang-btn",
                                    f"vl-lang-{code}",
                                    "vl-lang-active" if is_active else "vl-lang-idle",
                                ],
                            )
                            lang_buttons[code] = lang_btn

        # ── Tabs ──────────────────────────────────────────────────────
        with gr.Tabs() as tabs:
            with gr.Tab(t["tab_talk"]) as tab_talk:
                # ── Live mode card (the rung-switcher demo controller) ──
                mode_picker_buttons: dict[Mode, gr.Button] = {}
                mode_blurb_html: gr.HTML | None = None
                with gr.Group(elem_classes="vl-livemode"):
                    livemode_head_html = gr.HTML(_livemode_head_html(t))
                    if multi_rung:
                        with gr.Row(elem_classes="vl-livemode-body"):
                            with gr.Row(elem_classes="vl-switcher"):
                                for r in rungs:
                                    is_active = r.mode == initial_rung.mode
                                    btn = gr.Button(
                                        value=r.short,
                                        variant="primary" if is_active else "secondary",
                                        size="sm",
                                        elem_classes=[
                                            "vl-switcher-btn",
                                            f"vl-switcher-{r.mode.value}",
                                            "vl-switcher-active" if is_active else "vl-switcher-idle",
                                        ],
                                    )
                                    mode_picker_buttons[r.mode] = btn
                            destination_html = gr.HTML(_destination_html(initial_rung, settings, t))
                        mode_blurb_html = gr.HTML(_blurb_html(initial_rung, initial_locale))
                    else:
                        single_html = (
                            '<div class="vl-livemode-body">'
                            f'<div class="vl-livemode-single">'
                            f'<span class="vl-dot" style="background:{initial_rung.color};"></span>'
                            f'{initial_rung.label}'
                            f'</div>'
                            f'{_destination_html(initial_rung, settings, t)}'
                            '</div>'
                        )
                        destination_html = gr.HTML(single_html)
                        mode_blurb_html = gr.HTML(_blurb_html(initial_rung, initial_locale))

                with gr.Row(equal_height=False):
                    with gr.Column(scale=3):
                        with gr.Row(equal_height=True):
                            with gr.Column(scale=10, min_width=0):
                                mic_title_html = gr.HTML(_section_title_html(t["microphone"]))
                            with gr.Column(scale=2, min_width=120, elem_classes="vl-status-cell"):
                                status_html = gr.HTML(_status_html("idle", initial_locale))
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
                        transcript_title_html = gr.HTML(_section_title_html(t["transcript"], top=18))
                        chatbot = gr.Chatbot(
                            type="messages",
                            label="",
                            height=420,
                            show_copy_button=True,
                            show_label=False,
                            placeholder=_chatbot_placeholder_html(t),
                            avatar_images=(None, "https://learn.microsoft.com/favicon.ico"),
                        )

                    with gr.Column(scale=1, min_width=300):
                        settings_title_html = gr.HTML(_section_title_html(t["settings"]))
                        with gr.Group():
                            voice = gr.Dropdown(
                                choices=_voice_choices(initial_locale),
                                value=shared.voice,
                                label=t["voice"],
                                interactive=True,
                                elem_classes="vl-voice-picker",
                            )
                            instructions = gr.Textbox(
                                value=shared.instructions,
                                label=t["instructions"],
                                lines=6,
                                max_lines=10,
                                interactive=True,
                            )
                        with gr.Row(elem_classes="vl-button-row"):
                            apply_btn = gr.Button(t["apply"], variant="primary", size="sm", scale=1)
                            reset_btn = gr.Button(t["reset"], variant="secondary", size="sm", scale=1)
                        connection_title_html = gr.HTML(_section_title_html(t["connection"], top=18))
                        with gr.Group():
                            session_info = gr.Markdown(value=t["no_session"])
                            backend_accordion = gr.Accordion(t["backend_details"], open=False)
                            with backend_accordion:
                                backend_md = gr.Markdown(_backend_md(t))

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
                    shared.voice_type = _voice_type_lookup(shared.locale).get(v, "azure-standard")
                    shared.instructions = ins
                    return _status_html("idle", shared.locale)

                apply_btn.click(
                    fn=_apply_settings,
                    inputs=[voice, instructions],
                    outputs=[status_html],
                )

                def _reset_conversation() -> tuple[list, str]:
                    shared.reset_requested = True
                    return [], _status_html("idle", shared.locale)

                reset_btn.click(fn=_reset_conversation, inputs=None, outputs=[chatbot, status_html])

            with gr.Tab(t["tab_diff"]) as tab_diff:
                diff_intro_html = gr.HTML(_diff_intro_html(t))
                diff_body_html = gr.HTML(render_diffs_html(initial_locale))

            with gr.Tab(t["tab_about"]) as tab_about:
                about_md = gr.Markdown(_about_md(t))

        # ── Mode switcher wiring ─────────────────────────────────────
        if multi_rung:
            def _make_switch_handler(target_mode: Mode):
                target_rung = rung_by_mode[target_mode]

                def _switch() -> tuple:
                    # Mutate the live handler in place. The next time the
                    # WebRTC widget opens a stream (after the user clicks
                    # the mic), start_up() reads these new callables and
                    # dials the new WebSocket destination.
                    handler.connect_factory = target_rung.connect_factory
                    handler.make_session = target_rung.make_session
                    handler.name = target_rung.mode.value
                    shared.mode = target_rung.mode

                    t_cur = STRINGS[shared.locale]
                    dest_out = _destination_html(target_rung, settings, t_cur)
                    blurb_out = _blurb_html(target_rung, shared.locale)
                    session_out = (
                        f"_{t_cur['switched_to']} **{target_rung.label}**. {t_cur['click_mic']}._"
                    )
                    button_updates = tuple(
                        gr.update(
                            variant="primary" if r.mode == target_mode else "secondary",
                            elem_classes=[
                                "vl-switcher-btn",
                                f"vl-switcher-{r.mode.value}",
                                "vl-switcher-active" if r.mode == target_mode else "vl-switcher-idle",
                            ],
                        )
                        for r in rungs
                    )
                    return (dest_out, blurb_out, session_out, *button_updates)

                return _switch

            outputs = [destination_html, mode_blurb_html, session_info, *mode_picker_buttons.values()]
            for mode_key, btn in mode_picker_buttons.items():
                btn.click(fn=_make_switch_handler(mode_key), inputs=None, outputs=outputs)

        # ── Language switcher wiring ─────────────────────────────────
        def _make_locale_handler(target_locale: str):
            def _change_locale() -> tuple:
                shared.locale = target_locale
                # Reset voice + instructions to the locale's defaults so the
                # demo sounds right out of the gate. (Customer can still
                # tweak after — the textboxes stay editable.)
                voice_name, voice_type = DEFAULT_VOICE[target_locale]
                shared.voice = voice_name
                shared.voice_type = voice_type
                shared.instructions = DEFAULT_INSTRUCTIONS[target_locale]

                tt = STRINGS[target_locale]
                # Snapshot of the currently active rung (its identity didn't
                # change — only the locale-translated blurb did).
                current_rung = rung_by_mode.get(shared.mode or initial_rung.mode, initial_rung)

                lang_btn_updates = tuple(
                    gr.update(
                        elem_classes=[
                            "vl-lang-btn",
                            f"vl-lang-{code}",
                            "vl-lang-active" if code == target_locale else "vl-lang-idle",
                        ],
                    )
                    for _label, code in LOCALES
                )
                return (
                    _hero_main_html(tt),
                    f'<div class="vl-lang-label">{tt["language"]}</div>',
                    _livemode_head_html(tt),
                    _blurb_html(current_rung, target_locale),
                    _section_title_html(tt["microphone"]),
                    _section_title_html(tt["transcript"], top=18),
                    _section_title_html(tt["settings"], top=0),
                    _section_title_html(tt["connection"], top=18),
                    gr.update(
                        choices=_voice_choices(target_locale),
                        value=voice_name,
                        label=tt["voice"],
                    ),
                    gr.update(value=shared.instructions, label=tt["instructions"]),
                    gr.update(value=tt["apply"]),
                    gr.update(value=tt["reset"]),
                    tt["no_session"],
                    gr.update(label=tt["backend_details"]),
                    _backend_md(tt),
                    _status_html("idle", target_locale),
                    gr.update(label=tt["tab_talk"]),
                    gr.update(label=tt["tab_diff"]),
                    gr.update(label=tt["tab_about"]),
                    _diff_intro_html(tt),
                    render_diffs_html(target_locale),
                    _about_md(tt),
                    gr.update(placeholder=_chatbot_placeholder_html(tt)),
                    *lang_btn_updates,
                )
            return _change_locale

        locale_outputs = [
            hero_main_html,
            lang_label_html,
            livemode_head_html,
            mode_blurb_html,
            mic_title_html,
            transcript_title_html,
            settings_title_html,
            connection_title_html,
            voice,
            instructions,
            apply_btn,
            reset_btn,
            session_info,
            backend_accordion,
            backend_md,
            status_html,
            tab_talk,
            tab_diff,
            tab_about,
            diff_intro_html,
            diff_body_html,
            about_md,
            chatbot,
            *lang_buttons.values(),
        ]
        for code, lang_btn in lang_buttons.items():
            lang_btn.click(fn=_make_locale_handler(code), inputs=None, outputs=locale_outputs)

    return demo
