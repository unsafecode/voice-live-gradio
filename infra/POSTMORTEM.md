# Why this Azure Container Apps deploy doesn't work for the live demo

**TL;DR — keep the `voice-live-gradio` demo on your laptop. Don't deploy it
to ACA (or any container/PaaS host that doesn't terminate UDP).**

This branch (`feat/azure-deploy`) and the Bicep under `infra/` are kept as
an artefact so the next person who thinks "let's just `azd up` this for the
team" can read this note first and not burn an afternoon.

## What works

`azd up` against this repo correctly:

- Builds the image in ACR
- Spins up the Container App
- Wires the Foundry resource via UAMI + RBAC (Cognitive Services User)
- Exposes the Gradio UI on `https://<app>.<region>.azurecontainerapps.io/`

You can open the URL, see the UI, switch rungs, type a question, even
click the mic button — everything **except** the actual voice path works.

## What doesn't work — and why

This demo uses **FastRTC**, which is browser-side WebRTC talking to a
server-side `aiortc` peer running inside the container. WebRTC media flows
peer-to-peer over **UDP** (with TCP/TLS fallback through TURN).

Azure Container Apps ingress is an L7 reverse proxy. It forwards
**HTTP/HTTPS/WebSocket** to the container. It does **not** forward arbitrary
UDP. So:

1. The browser sends an SDP offer over the WebSocket (this works — it's
   HTTP).
2. ICE candidate gathering happens on both sides.
3. The browser's host candidate is its laptop IP (fine).
4. The server's host candidate is the container's internal `100.x.x.x`
   address — **unreachable from the browser** because ACA ingress doesn't
   route UDP back to the container.
5. ICE fails. The connection hangs at "Connecting…" forever. In the
   container logs you'll see `aioice` errors like
   `'NoneType' object has no attribute 'sendto'`.

WebRTC needs a TURN server when peers can't talk directly. We tried two
TURN-provider options before giving up:

### Attempt 1: Cloudflare TURN (via `fastrtc.get_cloudflare_turn_credentials_async`)

Works, but requires a Hugging Face token or Cloudflare account — i.e. an
external service. This repo is a public Azure-only demo; bringing a
third-party dependency for the demo to work is the wrong shape.

### Attempt 2: Azure Communication Services Network Traversal

ACS exposed a managed TURN service (`Microsoft.Communication/communicationServices`
+ `/networkTraversal/:issueRelayConfiguration`) that we could mint
short-lived credentials from via Entra ID. We wired it end-to-end:

- `voicelive_demo/rtc.py` — async ACS client returning a FastRTC-shaped
  `{ iceServers: [...] }` dict
- `infra/modules/acs.bicep` — ACS resource (global, dataLocation=Europe) +
  Contributor role to the container's UAMI
- `voicelive_demo/ui.py` — passes the dict to both `rtc_configuration`
  (browser) and `server_rtc_configuration` (server-side aiortc)
- `app_demo.py` / `app_realtime.py` / `app_voicelive.py` / `app_agent.py`
  — `asyncio.run(fetch_acs_turn_config())` at startup
- `pyproject.toml` — `azure-communication-networktraversal>=1.1.0b2`
  (only beta version available)

Deployed, looked healthy, then hit a `404 Page not found` from Front Door:

```
POST https://<acs>.europe.communication.azure.com/networkTraversal/:issueRelayConfiguration?api-version=2022-03-01-preview
HTTP/2 404
content-type: text/html
```

The Identity API on the same ACS resource (`POST /identities`) returns
`201 Created` — so it's not auth, not the resource, not the region. The
Network Traversal route is **gone from the data plane**.

Checking [the official Azure update](https://azure.microsoft.com/updates/retirement-notice-azure-communication-services-network-traversal-turn-public-preview-is-retiring/):

> Azure Communication Services Network Traversal (TURN) currently provides
> tokens to access our Transport Relays to use data transfer services. We
> will retire the feature by **October 31, 2026**. We will be performing a
> **scream test on October 27, 2025**, as part of this deprecation.

The scream test removed the data-plane routes; the SDK still ships but
hits a 404 from Front Door. ACS Network Traversal is effectively dead.

The Python SDK `azure-communication-networktraversal` was never promoted
out of beta (last release: `1.1.0b2`, Feb 2022 — already marked
`deprecated` in [the .NET SDK release table](https://raw.githubusercontent.com/Azure/azure-sdk/main/_data/releases/latest/dotnet-packages.csv)
with retirement date 2024-03-31).

### Other Azure-native options we did NOT try

- **Azure Front Door** — L7 only, doesn't proxy UDP. Same problem as ACA.
- **Azure Application Gateway** — same.
- **Azure Communication Services Calling** (`@azure/communication-calling`)
  — this is the official path forward per the ACS retirement notice, but
  it's a completely different SDK aimed at full call-management
  scenarios (rooms, participants, recordings). It is **not** a drop-in
  TURN provider for an arbitrary WebRTC peer like aiortc. Rewriting the
  demo around it would mean ripping out FastRTC, which defeats the
  purpose of this repo (showing how trivially you switch SDKs).
- **Self-hosted coturn on an Azure VM / Container Instance with public
  UDP** — works, but adds a second always-on resource the demo audience
  has to provision, defeats the "tiny, public, keyless" shape of this
  repo, and shifts the demo from "Foundry SDK delta" to "how to run
  coturn".
- **Azure Kubernetes Service with a UDP `LoadBalancer` Service** — same
  as coturn-on-VM but more pieces to explain.

None of those fit the demo's audience (engineering buyers evaluating the
Voice Live SDK delta in 5 minutes).

## What to do instead

**Run the demo locally.** WebRTC works fine on `localhost` (browser and
server are the same machine — no NAT, no TURN needed). The repo is set
up for this:

```bash
cd voice-live-gradio
uv sync
cp .env.example .env  # then fill in <your-foundry-resource>
az login --tenant <your-tenant>
uv run app.py
# → http://localhost:7860
```

See the top-level `README.md` for the per-peer setup walkthrough.

## What to do if you really need a hosted version

If a customer-facing hosted demo is a hard requirement, the smallest path
that preserves the SDK story is:

1. **Self-host coturn on an Azure VM** (B1s, ~$8/mo) with one public IP
   and UDP 3478 open. Configure it with a long-term auth user.
2. Set `TURN_URL` / `TURN_USERNAME` / `TURN_PASSWORD` as env vars on the
   container.
3. In `voicelive_demo/rtc.py`, replace `fetch_acs_turn_config()` with
   a function that returns
   `{"iceServers":[{"urls":[TURN_URL],"username":TURN_USERNAME,"credential":TURN_PASSWORD}]}`.
4. Keep this branch's `app.py` shells and `ui.py` changes —
   `server_rtc_configuration=rtc_configuration` on the WebRTC widget is
   still the correct fix.

Or: deploy on **Azure VM + Caddy + the same container image**. A VM has
real UDP. ACA does not. That's the whole story.

## What's in this branch worth keeping for that hypothetical rewrite

- `infra/main.bicep` + `infra/modules/{app,foundry,acr,monitoring,rbac}.bicep`
  — the ACA + Foundry + RBAC wiring is correct and works
- `voicelive_demo/rtc.py` — the async TURN-config fetcher pattern is the
  right shape; swap the ACS body for whatever TURN provider you pick
- `voicelive_demo/ui.py` — `server_rtc_configuration=rtc_configuration`
  on the FastRTC widget is the line that fixes the server side and
  isn't obvious from the FastRTC docs

## What to delete

- `infra/modules/acs.bicep` + the `acs` module call in `infra/main.bicep`
- `acsEndpoint` param in `infra/modules/app.bicep`
- `azure-communication-networktraversal` in `pyproject.toml` + `uv.lock`

…or just don't merge this branch and treat the whole thing as a
documented dead end. Either is fine.
