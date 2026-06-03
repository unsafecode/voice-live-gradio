// Minimal vanilla-JS client for the FastAPI WebSocket shell.
// Captures mic audio as 24 kHz PCM16, streams it over WS, plays back
// PCM16 received from the server through an AudioWorklet, and renders
// status + transcript events.

const SAMPLE_RATE = 24000;

const els = {
  rungs: document.getElementById("rungs"),
  locales: document.getElementById("locales"),
  voice: document.getElementById("voice"),
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
    input.addEventListener("change", refreshVoiceOptions);
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

function selectedRung() {
  return els.rungs.querySelector('input[name="rung"]:checked')?.value ?? "voicelive";
}

function selectedLocale() {
  return els.locales.querySelector('input[name="locale"]:checked')?.value ?? "en";
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
  const { voice, voice_type } = selectedVoicePayload();

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
      instructions: els.instructions.value.trim() || undefined,
    }));
    try {
      await startMic();
      state.connected = true;
      els.disconnect.disabled = false;
      els.rungs.disabled = true;
      els.locales.disabled = true;
      els.voice.disabled = true;
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
    els.rungs.disabled = false;
    els.locales.disabled = false;
    els.voice.disabled = false;
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
    buildRungRadios(cfg.rungs, cfg.default_rung);
    buildLocaleRadios(cfg.locales, browserLocale);
    refreshVoiceOptions();
    refreshInstructions();
    els.connect.disabled = false;
  } catch (err) {
    console.error("could not load config", err);
    setStatus("error");
  }
  els.connect.addEventListener("click", connect);
  els.disconnect.addEventListener("click", disconnect);
})();
