# Deploying the web shell to Azure Container Apps

> **Goal:** stand up a public URL where peers can demo the three-rung
> voice flow in a browser, without touching FastRTC / WebRTC / TURN.
>
> **Why this exists:** the Gradio + FastRTC variant (`app.py`) needs
> UDP and a TURN server, which Azure Container Apps' L7-only ingress
> cannot provide. The web shell (`app_web.py`) ships raw PCM16 frames
> over a regular WebSocket, so it deploys cleanly on ACA, App Service,
> Cloud Run, or any container platform that proxies WSS.

## Prerequisites

1. **Azure CLI ≥ 2.65** and **Azure Developer CLI ≥ 1.10**
   ```bash
   az version
   azd version
   ```
2. **An existing Azure AI Foundry resource** in the target subscription
   with:
   * a Realtime model deployment (e.g. `gpt-realtime-1.5`)
   * Voice Live enabled at the account level
   * (Optional) a Foundry Prompt Agent if you want rung 3 —
     see [`AGENT_SETUP.md`](AGENT_SETUP.md)
3. **Permissions on the target subscription** to create:
   * a resource group
   * Azure Container Registry
   * Azure Container Apps environment + app
   * Log Analytics workspace
   * a user-assigned managed identity
   * role assignments on the existing Foundry account (cross-RG)

## (Recommended) Per-tenant Azure CLI / azd isolation

If you juggle multiple Azure tenants, set up per-tenant config dirs so
this deploy can't accidentally land in the wrong subscription:

```bash
export TENANT_NICKNAME=mydemo  # any short label
mkdir -p "$HOME/.azure-tenants/$TENANT_NICKNAME"
mkdir -p "$HOME/.azd-tenants/$TENANT_NICKNAME"
export AZURE_CONFIG_DIR="$HOME/.azure-tenants/$TENANT_NICKNAME"
export AZD_CONFIG_DIR="$HOME/.azd-tenants/$TENANT_NICKNAME"

az login --tenant <your-tenant-id>
az account set --subscription "<your-subscription>"
az account show --query '{name:name, tenant:tenantId, id:id}' -o table
azd auth login --tenant-id <your-tenant-id>
```

Re-export both `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` in every new
terminal — they're per-shell.

## One-time setup

```bash
cd /path/to/voice-live-gradio
azd env new voicelive   # name your azd environment (any short label)
```

Then set the Foundry bindings — these are **required** (no defaults
ship in the Bicep — see `infra/main.bicepparam`):

```bash
azd env set AZURE_LOCATION              swedencentral
azd env set FOUNDRY_ACCOUNT_NAME        <your-foundry-account>
azd env set FOUNDRY_RESOURCE_GROUP      <rg-of-your-foundry>
azd env set AZURE_OPENAI_ENDPOINT       https://<your-foundry>.openai.azure.com
azd env set AZURE_VOICELIVE_ENDPOINT    wss://<your-foundry>.services.ai.azure.com/voice-live
azd env set AZURE_OPENAI_DEPLOYMENT_NAME gpt-realtime-1.5

# Optional — rung 3 (Voice Live + Foundry Agent). Leave unset to hide it.
azd env set AGENT_PROJECT_NAME          <your-foundry-project>
azd env set AGENT_ID                    <your-agent-id>

# Optional — set to true ONLY in Microsoft-internal MCAPS pilot subs
azd env set MCAPS_PILOT_POSTURE         false

# Optional — your principal id, for "developer also gets RBAC" convenience
azd env set AZURE_PRINCIPAL_ID          $(az ad signed-in-user show --query id -o tsv)
```

## Deploy

```bash
azd up
```

This will:

1. Provision a fresh resource group (named `rg-voicelive` by default)
2. Create UAMI → ACR → Log Analytics → ACA env → ACA app
3. Grant the UAMI:
   * `AcrPull` on the new ACR
   * `Cognitive Services User` on the BYO Foundry (for Voice Live + Realtime)
   * `Azure AI User` on the BYO Foundry (for the Agent rung)
4. Build the Dockerfile, push to ACR, swap the placeholder image on the ACA

**RBAC propagation is preempted by `dependsOn: [rbac]`** on the ACA module —
the first revision should pull cleanly without the usual ~60s wait.

## Verify

```bash
# Get the URL
WEB_URL=$(azd env get-value SERVICE_WEB_URI)
echo "$WEB_URL"

# Smoke-test
curl -fsS "$WEB_URL/health"          # → {"status":"ok"}
curl -fsS "$WEB_URL/api/config"      # → {"rungs":["realtime","voicelive"],…}

# Open the UI in a browser; click "Connect", grant mic, speak.
open "$WEB_URL"
```

If the page loads but `/health` is timing out, give the ACA replica
~20 seconds to finish cold-starting (the Dockerfile installs Gradio +
FastRTC even though the web shell doesn't use them — the image is
≈700 MB).

## Browser support

| Browser            | Status |
| ------------------ | ------ |
| Chrome ≥ 121       | ✅      |
| Edge ≥ 121         | ✅      |
| Firefox ≥ 122      | ✅      |
| Safari macOS ≥ 17  | ⚠️ pitch may be off — Safari ignores the AudioContext sampleRate hint |
| Safari iOS         | ⚠️ same; mic permission requires a user gesture (the Connect button handles this) |

The browser opens an `AudioContext` at 24 kHz; the recorder + player
worklets emit / consume 24 kHz mono PCM16 frames. On browsers that
honour the sampleRate hint, no resampling happens anywhere — the
browser handles device-rate conversion transparently.

## Update an existing deployment

```bash
# Code change only — rebuilds the image, pushes to ACR, swaps the running container.
azd deploy

# Bicep change only — applies the infra delta.
azd provision

# Both — same as `azd up`.
azd up
```

## Tear down

```bash
azd down --purge --force
```

This deletes the RG **and** the soft-deleted resources (LAW, ACR). The
BYO Foundry resource is left intact (it's not in the RG `azd` manages).

## Known limitations

* **No Application Insights** is provisioned. ACA console + system logs
  stream to the Log Analytics workspace created by the Bicep — query
  via `az containerapp logs show -n <app> -g <rg>` or the portal blade.
* **No private networking.** The ACA env is in a public managed network.
  For VNet-isolated deployments, switch the env's
  `vnetConfiguration.infrastructureSubnetId` and put a Private Endpoint
  on the BYO Foundry. (Out of scope for this demo template.)
* **Single replica.** `minReplicas: 1` / `maxReplicas: 3`. Each
  WebSocket connection is sticky to the replica that accepted it; with
  more than one replica, ACA's load balancer routes the *new* connection
  to a random replica. There is no shared session store.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `/health` returns 502 / times out | Container still cold-starting | Wait 20–40s after `azd deploy` finishes |
| Page loads, status stuck on `connecting` | Browser sent `config` but upstream never opened | Check `az containerapp logs show -n <app> -g <rg> --tail 50` — look for token errors or `cognitiveServices.azure.com/.default` failures |
| `FetchingKeyVaultSecretFailed: 401` in system logs | UAMI lacks `AcrPull` on the ACR (mis-labelled by ACA) | Re-run `azd provision` — RBAC propagation may have lagged |
| Voice Live works, Realtime fails | Foundry resource doesn't have the Realtime model deployed | Confirm `AZURE_OPENAI_DEPLOYMENT_NAME` matches an actual deployment |
| Agent rung not shown in /api/config | `AGENT_PROJECT_NAME` or `AGENT_ID` unset | `azd env set AGENT_…` then `azd provision` |
