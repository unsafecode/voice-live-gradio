"""Localisation strings for the demo UI.

The customer might be Italian; the model picks up the language from the
voice + transcription config; the *UI* picks it up from this module.

Add a locale by appending a key to every dict and the language switcher
in the Live mode card will surface it automatically.
"""
from __future__ import annotations

LOCALES: list[tuple[str, str]] = [
    ("🇺🇸  English",  "en"),
    ("🇮🇹  Italiano", "it"),
]

# Voice picker options per locale. The third tuple element is the
# ``voice_type`` Voice Live needs when sending ``session.update`` (HD
# voices are ``azure-standard``; for legacy neural voices we'd flip it).
VOICE_OPTIONS: dict[str, list[tuple[str, str, str]]] = {
    "en": [
        ("Ava — Azure Neural HD (default)", "en-US-Ava:DragonHDLatestNeural",    "azure-standard"),
        ("Jenny — Azure Neural HD",         "en-US-Jenny:DragonHDLatestNeural",  "azure-standard"),
        ("Davis — Azure Neural HD",         "en-US-Davis:DragonHDLatestNeural",  "azure-standard"),
        ("Guy — Azure Neural",              "en-US-GuyNeural",                   "azure-standard"),
        ("Brian — Azure Neural",            "en-US-BrianNeural",                 "azure-standard"),
        ("Alloy — OpenAI",                  "alloy",                             "azure-standard"),
        ("Nova — OpenAI",                   "nova",                              "azure-standard"),
        ("Shimmer — OpenAI",                "shimmer",                           "azure-standard"),
    ],
    "it": [
        ("Isabella — Azure Multilingual (default)", "it-IT-IsabellaMultilingualNeural", "azure-standard"),
        ("Giuseppe — Azure Multilingual",           "it-IT-GiuseppeMultilingualNeural", "azure-standard"),
        ("Alessio — Azure Multilingual",            "it-IT-AlessioMultilingualNeural",  "azure-standard"),
        ("Marta — Azure Neural",                    "it-IT-MartaNeural",                "azure-standard"),
        ("Diego — Azure Neural",                    "it-IT-DiegoNeural",                "azure-standard"),
        ("Elsa — Azure Neural",                     "it-IT-ElsaNeural",                 "azure-standard"),
        ("Nova — OpenAI",                           "nova",                             "azure-standard"),
        ("Shimmer — OpenAI",                        "shimmer",                          "azure-standard"),
    ],
}

DEFAULT_VOICE: dict[str, tuple[str, str]] = {
    "en": ("en-US-Ava:DragonHDLatestNeural",    "azure-standard"),
    "it": ("it-IT-IsabellaMultilingualNeural",  "azure-standard"),
}

# Realtime API voice catalog — locale-independent, OpenAI voice set only.
# Source: openai SDK `Voice` Literal (`alloy, ash, ballad, coral, echo, sage,
# shimmer, verse, marin, cedar`). Azure HD voices are NOT supported here;
# selecting one would be silently ignored by the Realtime endpoint.
REALTIME_VOICE_OPTIONS: list[tuple[str, str, str]] = [
    ("Alloy — OpenAI (default)",            "alloy",   "openai"),
    ("Ash — OpenAI",                        "ash",     "openai"),
    ("Ballad — OpenAI",                     "ballad",  "openai"),
    ("Coral — OpenAI",                      "coral",   "openai"),
    ("Echo — OpenAI",                       "echo",    "openai"),
    ("Sage — OpenAI",                       "sage",    "openai"),
    ("Shimmer — OpenAI",                    "shimmer", "openai"),
    ("Verse — OpenAI",                      "verse",   "openai"),
    ("Marin — OpenAI (newer models, HQ)",   "marin",   "openai"),
    ("Cedar — OpenAI (newer models, HQ)",   "cedar",   "openai"),
]

REALTIME_DEFAULT_VOICE: tuple[str, str] = ("alloy", "openai")

REALTIME_VOICE_NAMES: frozenset[str] = frozenset(
    name for (_label, name, _vtype) in REALTIME_VOICE_OPTIONS
)

# Voice Live cascade + native-audio model picker.
#
# Per Microsoft Learn (Azure AI Foundry Voice Live, fetched 2026-06-03), the
# pre-deployed managed model catalog on the Voice Live endpoint includes
# GPT-5.x cascade models (STT → LLM → TTS) and `gpt-realtime-*` native-audio
# SKUs. The customer just passes `?model=<name>` on the Voice Live WS URL —
# no Foundry deployment of their own is needed for anything in this list.
#
# Cascade-only on purpose: the Realtime rung (rung 1) requires a realtime
# SKU and has its own deployment-name field, and the Agent rung (rung 3)
# inherits the model from the Foundry agent. Only Voice Live exposes this
# free pick of any model in the catalog.
#
# Order is the order shown to the user. `gpt-5` is the default because (a)
# it matches what the customer's own production stack uses for the same
# scenario, (b) it's stable / GA, (c) it's the lowest-latency cascade.
VOICELIVE_MODELS: list[tuple[str, str]] = [
    ("GPT-5 (cascade, recommended)",           "gpt-5"),
    ("GPT-5.4 (newest cascade)",               "gpt-5.4"),
    ("GPT-5.3 Chat (dialogue-tuned)",          "gpt-5.3-chat"),
    ("GPT-5 Mini (lower cost cascade)",        "gpt-5-mini"),
    ("GPT-Realtime 1.5 (native audio, lowest latency)", "gpt-realtime-1.5"),
    ("GPT-Realtime Mini (native audio)",       "gpt-realtime-mini"),
]

DEFAULT_VOICELIVE_MODEL: str = "gpt-5"

VOICELIVE_MODEL_NAMES: frozenset[str] = frozenset(
    name for (_label, name) in VOICELIVE_MODELS
)

# Whisper / azure-fast-transcription both accept ISO 639-1 here.
TRANSCRIPTION_LANGUAGE: dict[str, str] = {
    "en": "en",
    "it": "it",
}

DEFAULT_INSTRUCTIONS: dict[str, str] = {
    "en": (
        "You are a friendly, concise voice assistant. Keep replies short — "
        "under 2 sentences unless the user explicitly asks for more. Speak naturally."
    ),
    "it": (
        "Sei un assistente vocale amichevole e conciso. Rispondi sempre in italiano. "
        "Mantieni le risposte brevi — meno di 2 frasi, a meno che l'utente non chieda "
        "esplicitamente di più. Parla in modo naturale."
    ),
}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "__locale__":           "en",
        "eyebrow":              "May 2026 · GA refresh",
        "subtitle":             "A drop-in switch from Azure OpenAI Realtime to Azure AI Foundry Voice Live — same SDK, one connect call.",
        "live_mode":            "Live mode",
        "live_hint":            "Switch any time — click the mic to (re)connect with the new destination.",
        "microphone":           "Microphone",
        "transcript":           "Transcript",
        "settings":             "Settings",
        "language":             "Interface & voice language",
        "voice":                "Voice",
        "instructions":         "System instructions",
        "apply":                "Apply",
        "reset":                "Reset",
        "voice_hint_realtime":  "Realtime uses the OpenAI voice set (alloy, ash, ballad, …). Switch to <b>Voice Live</b> for Azure Neural HD voices.",
        "voice_hint_voicelive": "Voice Live serves Azure Neural HD voices (locale-specific). OpenAI voices stay available too.",
        "connection":           "Connection",
        "backend_details":      "Backend details",
        "no_session":           "_No active session._",
        "switched_to":          "Switched to",
        "click_mic":            "Click the mic to (re)connect",
        "transcript_placeholder": "Conversation will appear here once you start talking.",
        "tab_talk":             "Talk",
        "tab_diff":             "Switch diff",
        "tab_about":            "About",
        "diff_title":           "How trivial is the switch?",
        "diff_lede":            'Three sibling files in <code>voicelive_demo/rungs/</code>, one per rung. All shared plumbing (UI, FastRTC pipe, audio queue, transcript fan-out) lives one directory up. Below is the entire delta — only the functions that actually change between rungs.',
        "foundry_endpoint":     "Foundry endpoint",
        "voicelive_wss":        "Voice Live WSS",
        "default_model":        "Default model",
        "auth":                 "Auth",
        "diff_lines":           "lines",
        "diff_fn_touched_one":  "1 function touched",
        "diff_fn_touched_many": "{n} functions touched",
        "diff_empty":           "No code changes in the focus functions.",
        "diff_section1_title":  "Azure OpenAI Realtime → Azure Voice Live",
        "diff_section1_lede":   "Same <code>AsyncAzureOpenAI</code> client, same <code>client.realtime.connect()</code> call. Three knobs change to point the SDK at the GA Voice Live endpoint.",
        "diff_section1_chip1":  "Same SDK",
        "diff_section1_chip2":  "Same call shape",
        "diff_section2_title":  "Voice Live → Voice Live + Foundry Agent",
        "diff_section2_lede":   "Same <code>connect_factory</code>. The <code>extra_query</code> dict is swapped: the model id is replaced by an agent id, project name, and short-lived agent access token.",
        "diff_section2_chip1":  "Same SDK",
        "diff_section2_chip2":  "Agent owns instructions",
    },
    "it": {
        "__locale__":           "it",
        "eyebrow":              "Maggio 2026 · Aggiornamento GA",
        "subtitle":             "Un cambio drop-in da Azure OpenAI Realtime ad Azure AI Foundry Voice Live — stesso SDK, una sola chiamata di connessione.",
        "live_mode":            "Modalità live",
        "live_hint":            "Cambia quando vuoi — clicca il microfono per (ri)connetterti alla nuova destinazione.",
        "microphone":           "Microfono",
        "transcript":           "Trascrizione",
        "settings":             "Impostazioni",
        "language":             "Lingua interfaccia e voce",
        "voice":                "Voce",
        "instructions":         "Istruzioni di sistema",
        "apply":                "Applica",
        "reset":                "Reimposta",
        "voice_hint_realtime":  "Realtime usa il set di voci OpenAI (alloy, ash, ballad, …). Passa a <b>Voice Live</b> per le voci Azure Neural HD.",
        "voice_hint_voicelive": "Voice Live offre voci Azure Neural HD (specifiche per la lingua). Le voci OpenAI restano disponibili.",
        "connection":           "Connessione",
        "backend_details":      "Dettagli backend",
        "no_session":           "_Nessuna sessione attiva._",
        "switched_to":          "Passato a",
        "click_mic":            "Clicca il microfono per (ri)connetterti",
        "transcript_placeholder": "La conversazione apparirà qui una volta iniziato a parlare.",
        "tab_talk":             "Parla",
        "tab_diff":             "Diff del passaggio",
        "tab_about":            "Informazioni",
        "diff_title":           "Quanto è banale il passaggio?",
        "diff_lede":            'Tre file fratelli in <code>voicelive_demo/rungs/</code>, uno per gradino. Tutto il resto (UI, pipe FastRTC, coda audio, fan-out della trascrizione) è condiviso una directory più su. Qui sotto c\'è l\'intera differenza — solo le funzioni che cambiano davvero da un gradino all\'altro.',
        "foundry_endpoint":     "Endpoint Foundry",
        "voicelive_wss":        "WSS Voice Live",
        "default_model":        "Modello predefinito",
        "auth":                 "Autenticazione",
        "diff_lines":           "righe",
        "diff_fn_touched_one":  "1 funzione modificata",
        "diff_fn_touched_many": "{n} funzioni modificate",
        "diff_empty":           "Nessuna modifica di codice nelle funzioni chiave.",
        "diff_section1_title":  "Azure OpenAI Realtime → Azure Voice Live",
        "diff_section1_lede":   "Stesso client <code>AsyncAzureOpenAI</code>, stessa chiamata <code>client.realtime.connect()</code>. Tre piccoli kwargs cambiano per puntare l'SDK all'endpoint GA Voice Live.",
        "diff_section1_chip1":  "Stesso SDK",
        "diff_section1_chip2":  "Stessa forma di chiamata",
        "diff_section2_title":  "Voice Live → Voice Live + Foundry Agent",
        "diff_section2_lede":   "Stesso <code>connect_factory</code>. Il dict <code>extra_query</code> viene sostituito: l'id del modello è rimpiazzato da un id agente, nome progetto e token di accesso effimero.",
        "diff_section2_chip1":  "Stesso SDK",
        "diff_section2_chip2":  "L'agente possiede le istruzioni",
    },
}

STATUS_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "idle":       "Idle",
        "connecting": "Connecting",
        "listening":  "Listening",
        "thinking":   "Thinking",
        "speaking":   "Speaking",
        "error":      "Error",
    },
    "it": {
        "idle":       "Inattivo",
        "connecting": "Connessione…",
        "listening":  "In ascolto",
        "thinking":   "Sto pensando",
        "speaking":   "Sto parlando",
        "error":      "Errore",
    },
}

# Per-rung blurb translations. The blurbs live in rungs/__init__.py
# for the English default; we override them here when the UI switches
# locale.
RUNG_BLURBS: dict[str, dict[str, str]] = {
    "en": {
        "realtime":  "Direct GA Realtime API. OpenAI voices. The before.",
        "voicelive": "Same SDK, three small kwargs. Azure Neural HD voices, semantic VAD, server-side echo cancel & noise reduction.",
        "agent":     "Same connect call, agent triplet in extra_query. The hosted agent owns instructions & tools.",
    },
    "it": {
        "realtime":  "API Realtime GA diretta. Voci OpenAI. Il prima.",
        "voicelive": "Stesso SDK, tre piccoli kwargs. Voci Azure Neural HD, VAD semantico, cancellazione eco e riduzione rumore lato server.",
        "agent":     "Stessa chiamata connect, tripletta dell'agent in extra_query. L'agent hosted gestisce istruzioni e strumenti.",
    },
}
