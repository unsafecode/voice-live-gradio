# Peer setup — run this demo on your laptop in 5 minutes

This is the **single, self-contained guide** to get `voice-live-gradio` running
on your machine so you can demo "Azure OpenAI Realtime → Voice Live in 3 lines"
to a customer over a Teams call.

> 🛑 **Why no hosted URL?** WebRTC media needs UDP, and Azure Container
> Apps ingress is L7-only — see [`infra/POSTMORTEM.md`](../infra/POSTMORTEM.md)
> on the `feat/azure-deploy` branch for the full story. The demo runs on
> your laptop, you screen-share, audio works because everything is on
> `localhost`.

---

## What you'll see at the end

`http://localhost:7860` opens to a Gradio UI with three "rungs" in a header
pill (Realtime · Voice Live · Agent), a mic button, and a **🧩 View the
diff** tab that renders the literal source-code delta between the rungs.
Click the mic, speak, the model talks back through your speakers, and the
transcript streams into the page.

That's the whole demo. ~3 minutes once you've done the one-time setup.

---

## Prerequisites

You need **all** of these. None take more than a couple of minutes.

| | What | Why |
|---|---|---|
| 1 | **Azure subscription** with permission to create Foundry resources and assign roles | The demo authenticates against Foundry via your Entra identity |
| 2 | **Azure AI Foundry resource** in a [Voice-Live-supported region](https://learn.microsoft.com/azure/ai-services/speech-service/regions?tabs=voice-live#regions) (Sweden Central / East US 2 / West US 2 are the safe bets) | Where the realtime model lives |
| 3 | **A realtime model deployed** in that Foundry resource (`gpt-realtime-1.5` recommended) | The thing you're talking to |
| 4 | `Cognitive Services User` role on the Foundry resource — assigned to **you** (your Entra user) | DefaultAzureCredential needs a token your Foundry account will accept |
| 5 | **Python ≥ 3.13**, **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, **ffmpeg**, **az CLI ≥ 2.65** | Local toolchain |

The rest of this doc walks each one of these end to end.

---

## 0. Install the local toolchain (one-time, ~3 min)

**macOS** (Homebrew):

```bash
brew install uv ffmpeg azure-cli
# Python 3.13 — uv will install it on demand, but you can pre-install:
brew install python@3.13
```

**Windows** (winget):

```powershell
winget install --id=astral-sh.uv -e
winget install --id=Gyan.FFmpeg -e
winget install --id=Microsoft.AzureCLI -e
winget install --id=Python.Python.3.13 -e
```

**Linux** (Ubuntu/Debian):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo apt-get update && sudo apt-get install -y ffmpeg
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

Verify:

```bash
uv --version && ffmpeg -version | head -1 && az --version | head -1
```

---

## 1. Get an Azure AI Foundry resource

You have two paths. Pick one.

### Path A — reuse an existing Foundry resource you already have access to

Skip to step 2.

### Path B — provision a new one (≈ 2 min)

Sweden Central has the broadest realtime model catalog as of May 2026.

```bash
az login                              # add --tenant <tenant-id> if you span tenants
SUB="<your-subscription-id-or-name>"
az account set --subscription "$SUB"

RG="rg-voicelive-demo"
ACCOUNT="aif-voicelive-$RANDOM"       # must be globally unique
LOCATION="swedencentral"

az group create -n "$RG" -l "$LOCATION"

az cognitiveservices account create \
  --name "$ACCOUNT" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --kind AIServices \
  --sku S0 \
  --custom-domain "$ACCOUNT" \
  --yes

echo "Endpoint:   https://${ACCOUNT}.openai.azure.com"
echo "WSS:        wss://${ACCOUNT}.services.ai.azure.com/voice-live"
```

Note `$ACCOUNT` and `$RG` — you'll use them in step 3.

---

## 2. Deploy a realtime model

In the Foundry portal (or `az`), deploy a realtime model. Recommended:
**`gpt-realtime-1.5`** version `2026-02-23` — currently the newest model
Voice Live serves region-wide, keeps the rung-switching demo symmetric.

```bash
# Replace with your account + RG from step 1 (or your existing ones)
ACCOUNT="<your-foundry-account>"
RG="<your-foundry-rg>"

az cognitiveservices account deployment create \
  --resource-group "$RG" \
  --name "$ACCOUNT" \
  --deployment-name "gpt-realtime-1.5" \
  --model-name "gpt-realtime-1.5" \
  --model-version "2026-02-23" \
  --model-format "OpenAI" \
  --sku-name "GlobalStandard" \
  --sku-capacity 1
```

If your region doesn't list `gpt-realtime-1.5`, swap in whatever realtime
model the [region serves](https://learn.microsoft.com/azure/ai-services/openai/concepts/models?tabs=global-standard%2Cstandard-chat-completions#standard-deployment-model-availability)
(`gpt-realtime`, `gpt-realtime-mini`, `gpt-4o-realtime-preview`, etc.) —
just remember the deployment name for step 3.

---

## 3. Grant yourself the `Cognitive Services User` role

This is the one step people forget and then get a 401 on. **Don't skip.**

```bash
ACCOUNT="<your-foundry-account>"
RG="<your-foundry-rg>"

ME=$(az ad signed-in-user show --query id -o tsv)
SCOPE=$(az cognitiveservices account show -n "$ACCOUNT" -g "$RG" --query id -o tsv)

az role assignment create \
  --assignee-object-id "$ME" \
  --assignee-principal-type User \
  --role "Cognitive Services User" \
  --scope "$SCOPE"

# Sanity-check
az role assignment list --assignee "$ME" --scope "$SCOPE" -o table
```

Wait ~30 seconds for the assignment to propagate before step 4.

---

## 4. Clone, configure, run

```bash
git clone https://github.com/unsafecode/voice-live-gradio
cd voice-live-gradio

# Configure
cp .env.example .env
# Open .env in your editor, then:
#  - set AZURE_OPENAI_ENDPOINT     to https://<your-foundry-account>.openai.azure.com
#  - set AZURE_VOICELIVE_ENDPOINT  to wss://<your-foundry-account>.services.ai.azure.com/voice-live
#  - set AZURE_OPENAI_DEPLOYMENT_NAME to the deployment name from step 2
# (Leave AGENT_PROJECT_NAME / AGENT_ID blank — Agent rung is optional.)

# Install dependencies (creates .venv automatically)
uv sync

# Make sure az is logged into the tenant that owns the Foundry resource
az login                              # add --tenant <id> if multi-tenant

# Run
uv run app.py
```

You should see:

```
[voice-live-demo] MODE=demo → launching app_demo
[voice-live-demo] Listening on http://0.0.0.0:7860
```

Open <http://localhost:7860>, grant the browser mic permission, click the
mic button, speak.

---

## 5. Demo to a customer over a Teams call

The whole demo runs on **your localhost**. To show it to someone else:

1. Start the app: `uv run app.py`
2. Open `http://localhost:7860` in your browser, get the mic working
   yourself first (one quick test sentence — *"hello, can you hear me?"*)
3. **Share your browser tab** in Teams with **"Include sound"** ticked.
   This streams the model's audio output to the call.
4. Your local microphone is what the model hears. Speak normally — the
   customer hears your voice through Teams (because you're on the call)
   AND the model's reply through your shared tab.
5. Demo flow:
   - Click between **Realtime** / **Voice Live** / **Agent** rungs in
     the header pill. Click the mic to (re-)connect after each switch.
     ~2 seconds per switch.
   - Open the **🧩 View the diff** tab. Show the literal source delta.
     The two diff cards render `voicelive_demo/rungs/realtime.py` vs
     `…/voicelive.py` and `…/voicelive.py` vs `…/agent.py` directly from
     the running code. "Three lines. Same SDK."
   - Use the **language switcher** (top-right) to swap to Italian if
     the customer speaks Italian — the UI, the voice, and the
     transcription language all flip atomically.

> 💡 Don't share your full screen. Share **the browser tab**. The "Include
> sound" toggle only appears on tab/window sharing, not full-screen sharing
> on most Teams clients.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Missing required environment variables` on launch | `.env` not edited — re-read step 4 |
| `401 Unauthorized` on first mic click | Step 3 was skipped or hasn't propagated. Wait 60 s. Confirm with `az role assignment list --assignee $(az ad signed-in-user show --query id -o tsv) --scope <foundry-scope>` |
| `403 Forbidden` | Token was acquired against the wrong tenant. `az logout && az login --tenant <id>`, restart the app |
| `Click to Access Microphone` button does nothing | Browser blocked the mic. Click the 🔒 in the address bar → Site settings → allow Microphone for `localhost:7860` → refresh |
| `429` after a few turns | PAYG TPM throttle on the realtime deployment. Bump capacity in the Foundry portal |
| Port 7860 already in use | `PORT=7861 uv run app.py` |
| WSS errors mentioning `extra_query` / `404` from `services.ai.azure.com/voice-live` | `AZURE_VOICELIVE_ENDPOINT` typo. Must be exactly `wss://<account>.services.ai.azure.com/voice-live` (no trailing slash, no `/api`, no region path) |
| Italian voice mispronounces names or treats statements as questions | Open **System instructions** in the UI and add `Reply in Italian. Speak in clear, neutral statements without rising intonation unless the sentence is a question.` Customer feedback we've heard for `it-IT-Alessio:DragonHDLatestNeural` — `Marta` / `Diego` / `Elsa` (standard Neural) are sometimes more reliable on short phrases |
| Customer on the Teams call can't hear the model | You forgot to tick **Include sound** when sharing the tab. Re-share with sound on |

---

## Bonus — run the benchmark live

If the customer asks "but is Voice Live actually slower?", you can run the
benchmark in front of them. Takes ~2 min for the default 5-scenario matrix.

```bash
uv run python -m benchmark.run --iterations 3
```

Output: a markdown report under `benchmark/output/<timestamp>/report.md`
with p50 / p95 / coefficient-of-variation per scenario, plus per-turn
WAVs you can play back. The repo's README has the full matrix syntax.

---

## What this demo intentionally does **not** show

- **A hosted public URL** — see top of this file. ACA can't proxy UDP for
  WebRTC. If you need a hosted version for a customer with no laptop
  setup, the smallest path is "self-host coturn on an Azure VM"
  (`infra/POSTMORTEM.md` on the `feat/azure-deploy` branch explains
  exactly what changes).
- **A Foundry Agent flow** with custom tools — that's the third rung
  (`agent.py`) which auto-hides until you set `AGENT_ID` +
  `AGENT_PROJECT_NAME`. If the customer asks about agents, point them
  at the canonical [Voice Live + Agents quickstart](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-agents-quickstart)
  and offer to plug in their agent ID live.
- **A production-grade hosting story.** This is a *demo* — single
  process, single replica, local WebRTC. For production patterns talk
  to the GBB Foundry team about the `foundry-hosted-agents` and
  `foundry-mcp-aca` skills.

---

## Where to learn more

- Top-level [README.md](../README.md) — what's in the box, the diff,
  models, all CLI flags
- [`voicelive_demo/rungs/realtime.py`](../voicelive_demo/rungs/realtime.py),
  [`voicelive.py`](../voicelive_demo/rungs/voicelive.py),
  [`agent.py`](../voicelive_demo/rungs/agent.py) — the three rungs.
  Tiny, surgical, read top-to-bottom. The Switch tab in the UI renders
  these live
- [Voice Live overview](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
- [Voice Live API reference (2025-10-01)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2025-10-01)
- [Azure OpenAI Realtime concepts](https://learn.microsoft.com/azure/ai-services/openai/concepts/realtime-audio)

If something in this guide is wrong or out of date, please open an issue
on the repo.
