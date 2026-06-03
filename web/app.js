// Minimal vanilla-JS client for the FastAPI WebSocket shell.
// Captures mic audio as 24 kHz PCM16, streams it over WS, plays back
// PCM16 received from the server through an AudioWorklet, and renders
// status + transcript events.

const SAMPLE_RATE = 24000;

const els = {
  presets: document.getElementById("presets"),
  rungs: document.getElementById("rungs"),
  locales: document.getElementById("locales"),
  voice: document.getElementById("voice"),
  modelRow: document.getElementById("modelRow"),
  modelHint: document.getElementById("modelHint"),
  model: document.getElementById("model"),
  connect: document.getElementById("connectBtn"),
  disconnect: document.getElementById("disconnectBtn"),
  status: document.getElementById("status"),
  transcript: document.getElementById("transcript"),
  instructions: document.getElementById("instructions"),
};

const RUNG_LABELS = {
  realtime: "Azure OpenAI Realtime",
  voicelive: "Azure Voice Live",
  agent: "Voice Live + Foundry Agent",
};

const DEFAULT_INSTRUCTIONS = {
  en: "You are a friendly, concise voice assistant. Keep replies short — under 2 sentences unless the user explicitly asks for more. Speak naturally.",
  it: "Sei un assistente vocale amichevole e conciso. Rispondi sempre in italiano. Mantieni le risposte brevi — meno di 2 frasi, a meno che l'utente non chieda esplicitamente di più. Parla in modo naturale.",
};

const state = {
  ws: null,
  audioCtx: null,
  micStream: null,
  recorderNode: null,
  playerNode: null,
  connected: false,
  cfg: null,
  // Track which locale generated the current instructions textarea content
  // so a language switch can refresh it without nuking user edits.
  instructionsLocale: null,
  // Which preset is currently applied. Cleared to "default" the moment
  // the user manually touches voice / locale / model / instructions so
  // the radio reflects reality.
  activePreset: "default",
};

function setStatus(status) {
  els.status.textContent = status;
  els.status.dataset.state = status;
}

function addMessage(role, content) {
  const li = document.createElement("li");
  li.className = role;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role;
  const body = document.createElement("span");
  body.className = "body";
  body.textContent = content;
  li.appendChild(who);
  li.appendChild(body);
  els.transcript.appendChild(li);
  els.transcript.scrollTop = els.transcript.scrollHeight;
}

async function loadConfig() {
  const res = await fetch("/api/config");
  if (!res.ok) throw new Error(`/api/config returned ${res.status}`);
  return res.json();
}

function buildPresetRadios(presets, defaultPreset) {
  els.presets.innerHTML = "<legend>Preset</legend>";
  presets.forEach((p) => {
    const id = `preset-${p.key}`;
    const label = document.createElement("label");
    label.setAttribute("for", id);
    label.title = p.description || "";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "preset";
    input.id = id;
    input.value = p.key;
    if (p.key === defaultPreset) input.checked = true;
    input.addEventListener("change", () => applyPreset(p.key));
    const span = document.createElement("span");
    span.textContent = p.label;
    label.appendChild(input);
    label.appendChild(span);
    els.presets.appendChild(label);
  });
  els.presets.disabled = false;
}

function buildRungRadios(rungs, defaultRung) {
  els.rungs.innerHTML = "<legend>Rung</legend>";
  rungs.forEach((rung) => {
    const id = `rung-${rung}`;
    const label = document.createElement("label");
    label.setAttribute("for", id);
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "rung";
    input.id = id;
    input.value = rung;
    if (rung === defaultRung) input.checked = true;
    input.addEventListener("change", () => {
      refreshVoiceOptions();
      refreshModelVisibility();
    });
    const span = document.createElement("span");
    span.textContent = RUNG_LABELS[rung] ?? rung;
    label.appendChild(input);
    label.appendChild(span);
    els.rungs.appendChild(label);
  });
  els.rungs.disabled = false;
}

function buildLocaleRadios(locales, defaultLocale) {
  els.locales.innerHTML = "<legend>Language</legend>";
  locales.forEach(({ label: lbl, code }) => {
    const id = `loc-${code}`;
    const label = document.createElement("label");
    label.setAttribute("for", id);
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "locale";
    input.id = id;
    input.value = code;
    if (code === defaultLocale) input.checked = true;
    input.addEventListener("change", () => {
      markPresetCustomised();
      refreshVoiceOptions();
      refreshInstructions();
    });
    const span = document.createElement("span");
    span.textContent = lbl;
    label.appendChild(input);
    label.appendChild(span);
    els.locales.appendChild(label);
  });
  els.locales.disabled = false;
}

function buildModelOptions(models, defaultModel) {
  els.model.innerHTML = "";
  models.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.name;
    opt.textContent = m.label;
    if (m.name === defaultModel) opt.selected = true;
    els.model.appendChild(opt);
  });
  els.model.disabled = false;
  els.model.addEventListener("change", markPresetCustomised);
}

function selectedPreset() {
  return els.presets.querySelector('input[name="preset"]:checked')?.value ?? "default";
}

function selectedRung() {
  return els.rungs.querySelector('input[name="rung"]:checked')?.value ?? "voicelive";
}

function selectedLocale() {
  return els.locales.querySelector('input[name="locale"]:checked')?.value ?? "en";
}

function selectedModel() {
  return els.model.value || state.cfg?.default_voicelive_model || "";
}

function voicesForCurrent() {
  const rung = selectedRung();
  const locale = selectedLocale();
  if (rung === "realtime") {
    return { list: state.cfg.openai_voices, defaultVoice: state.cfg.default_openai_voice };
  }
  return {
    list: state.cfg.azure_voices[locale] ?? state.cfg.azure_voices.en,
    defaultVoice: state.cfg.default_azure_voice[locale] ?? state.cfg.default_azure_voice.en,
  };
}

function refreshVoiceOptions() {
  if (!state.cfg) return;
  const { list, defaultVoice } = voicesForCurrent();
  els.voice.innerHTML = "";
  list.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = `${v.name}|${v.type}`;
    opt.textContent = v.label;
    if (v.name === defaultVoice.name && v.type === defaultVoice.type) {
      opt.selected = true;
    }
    els.voice.appendChild(opt);
  });
  els.voice.disabled = false;
  // Re-bind every refresh — innerHTML reset blew away previous listeners.
  els.voice.addEventListener("change", markPresetCustomised, { once: true });
}

function refreshModelVisibility() {
  // Model picker is meaningful only on the Voice Live rung. Realtime is
  // pinned to its `gpt-realtime-*` deployment (env-controlled), and the
  // Agent rung inherits the model from the Foundry agent definition.
  const isVoiceLive = selectedRung() === "voicelive";
  els.modelRow.hidden = !isVoiceLive;
  els.modelHint.hidden = !isVoiceLive;
}

function refreshInstructions() {
  const locale = selectedLocale();
  const current = els.instructions.value.trim();
  const previousDefault = state.instructionsLocale
    ? DEFAULT_INSTRUCTIONS[state.instructionsLocale]
    : null;
  // Only replace if the user hasn't typed their own prompt
  if (!current || current === previousDefault) {
    els.instructions.value = DEFAULT_INSTRUCTIONS[locale] ?? DEFAULT_INSTRUCTIONS.en;
    state.instructionsLocale = locale;
  }
}

function detectBrowserLocale(supported) {
  const codes = supported.map((l) => l.code);
  const nav = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || "en"])
    .map((s) => (s || "").toLowerCase().split(/[-_]/)[0]);
  return nav.find((c) => codes.includes(c)) ?? "en";
}

function selectedVoicePayload() {
  const [name, type] = (els.voice.value || "").split("|");
  if (!name) {
    const { defaultVoice } = voicesForCurrent();
    return { voice: defaultVoice.name, voice_type: defaultVoice.type };
  }
  return { voice: name, voice_type: type };
}

// Apply a server-defined preset bundle. The server-side `apply_preset`
// is authoritative — the browser only mirrors the obvious UI fields so
// the user can SEE what changed before they hit Connect. The actual
// instructions/locale/model passed to Voice Live are decided server-side
// from the `preset` field in the WS handshake.
function applyPreset(presetKey) {
  state.activePreset = presetKey;
  const preset = (state.cfg?.presets ?? []).find((p) => p.key === presetKey);
  if (!preset) return;

  if (preset.forces_voice_live_rung) {
    const vl = els.rungs.querySelector('input[name="rung"][value="voicelive"]');
    if (vl && !vl.checked) vl.checked = true;
  }

  if (preset.locale) {
    const loc = els.locales.querySelector(`input[name="locale"][value="${preset.locale}"]`);
    if (loc) loc.checked = true;
  }

  // Refresh voice list now that rung + locale may have changed.
  refreshVoiceOptions();
  refreshModelVisibility();

  if (preset.voice) {
    const voiceVal = `${preset.voice}|${preset.voice_type || "azure-standard"}`;
    if ([...els.voice.options].some((o) => o.value === voiceVal)) {
      els.voice.value = voiceVal;
    }
  }

  if (preset.model && [...els.model.options].some((o) => o.value === preset.model)) {
    els.model.value = preset.model;
  }

  // The server's `presets.py` owns the prompt — we just clear the textarea
  // so stale English copy doesn't mislead the user before Connect.
  if (presetKey !== "default") {
    els.instructions.value = "";
    els.instructions.placeholder = `Using preset “${preset.label}” — server-defined prompt will be applied on Connect.`;
    state.instructionsLocale = null;
  } else {
    els.instructions.placeholder = "System prompt...";
    refreshInstructions();
  }
}

// Called whenever the user manually edits a field controlled by a preset.
// Snaps the preset back to "default" so we don't lie about an active bundle.
function markPresetCustomised() {
  if (state.activePreset === "default") return;
  state.activePreset = "default";
  const def = els.presets.querySelector('input[name="preset"][value="default"]');
  if (def) def.checked = true;
  els.instructions.placeholder = "System prompt...";
}

function setControlsLocked(locked) {
  els.presets.disabled = locked;
  els.rungs.disabled = locked;
  els.locales.disabled = locked;
  els.voice.disabled = locked;
  els.model.disabled = locked;
  els.instructions.disabled = locked;
}

async function ensureAudio() {
  if (state.audioCtx) return;
  state.audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
  if (state.audioCtx.sampleRate !== SAMPLE_RATE) {
    console.warn(
      `AudioContext landed at ${state.audioCtx.sampleRate} Hz instead of ${SAMPLE_RATE} Hz. ` +
      `Audio will be played back at the wrong speed. ` +
      `iOS Safari ignores the sampleRate hint — use Chrome / Edge / Firefox for now.`,
    );
  }
  await state.audioCtx.audioWorklet.addModule("/static/recorder-worklet.js");
  await state.audioCtx.audioWorklet.addModule("/static/player-worklet.js");
  state.playerNode = new AudioWorkletNode(state.audioCtx, "pcm-player");
  state.playerNode.connect(state.audioCtx.destination);
}

async function startMic() {
  state.micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
      sampleRate: SAMPLE_RATE,
    },
  });
  const source = state.audioCtx.createMediaStreamSource(state.micStream);
  state.recorderNode = new AudioWorkletNode(state.audioCtx, "pcm-recorder");
  state.recorderNode.port.onmessage = (event) => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.send(event.data);
    }
  };
  source.connect(state.recorderNode);
}

function stopMic() {
  if (state.recorderNode) {
    try { state.recorderNode.disconnect(); } catch {}
    state.recorderNode = null;
  }
  if (state.micStream) {
    state.micStream.getTracks().forEach((t) => t.stop());
    state.micStream = null;
  }
}

async function connect() {
  if (state.connected) return;
  els.connect.disabled = true;
  setStatus("connecting");

  try {
    await ensureAudio();
    if (state.audioCtx.state === "suspended") await state.audioCtx.resume();
  } catch (err) {
    console.error("audio init failed", err);
    setStatus("error");
    els.connect.disabled = false;
    return;
  }

  const rung = selectedRung();
  const locale = selectedLocale();
  const preset = selectedPreset();
  const { voice, voice_type } = selectedVoicePayload();
  // Model field is meaningful for Voice Live only; sent unconditionally
  // (server only acts on it for the Voice Live rung) so the browser
  // stays dumb about per-rung wiring.
  const model = selectedModel();

  const wsProto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${wsProto}://${location.host}/ws/${rung}`;
  const ws = new WebSocket(url);
  ws.binaryType = "arraybuffer";
  state.ws = ws;

  ws.onopen = async () => {
    ws.send(JSON.stringify({
      type: "config",
      voice,
      voice_type,
      locale,
      model: model || undefined,
      preset: preset || undefined,
      // Don't send our local English/Italian default — when a preset is
      // active the server owns the full prompt, and when it isn't, an
      // empty `instructions` lets the server keep its SharedState default.
      instructions:
        preset && preset !== "default"
          ? undefined
          : els.instructions.value.trim() || undefined,
    }));
    try {
      await startMic();
      state.connected = true;
      els.disconnect.disabled = false;
      setControlsLocked(true);
    } catch (err) {
      console.error("mic start failed", err);
      setStatus("error");
      ws.close();
    }
  };

  ws.onmessage = (event) => {
    if (typeof event.data === "string") {
      let payload;
      try { payload = JSON.parse(event.data); } catch { return; }
      switch (payload.type) {
        case "status":
          setStatus(payload.status);
          break;
        case "message":
          addMessage(payload.role, payload.content);
          break;
        case "session":
          console.info(`session ${payload.session_id} model=${payload.model}`);
          break;
        case "clear_playback":
          if (state.playerNode) state.playerNode.port.postMessage("clear");
          break;
        default:
          break;
      }
    } else if (event.data instanceof ArrayBuffer) {
      if (state.playerNode) state.playerNode.port.postMessage(event.data, [event.data]);
    }
  };

  ws.onerror = (event) => {
    console.error("ws error", event);
    setStatus("error");
  };

  ws.onclose = () => {
    state.connected = false;
    state.ws = null;
    stopMic();
    els.connect.disabled = false;
    els.disconnect.disabled = true;
    setControlsLocked(false);
    setStatus("offline");
  };
}

function disconnect() {
  if (state.ws) {
    try { state.ws.close(); } catch {}
  }
}

(async () => {
  setStatus("offline");
  try {
    const cfg = await loadConfig();
    state.cfg = cfg;
    const browserLocale = detectBrowserLocale(cfg.locales);
    buildPresetRadios(cfg.presets ?? [], cfg.default_preset ?? "default");
    buildRungRadios(cfg.rungs, cfg.default_rung);
    buildLocaleRadios(cfg.locales, browserLocale);
    buildModelOptions(cfg.voicelive_models ?? [], cfg.default_voicelive_model ?? "");
    refreshVoiceOptions();
    refreshModelVisibility();
    refreshInstructions();
    els.connect.disabled = false;
  } catch (err) {
    console.error("could not load config", err);
    setStatus("error");
  }
  els.connect.addEventListener("click", connect);
  els.disconnect.addEventListener("click", disconnect);
})();
