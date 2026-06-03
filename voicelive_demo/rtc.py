"""ACS-backed TURN credentials for FastRTC on Azure Container Apps.

ACA ingress only supports TCP/HTTP/HTTPS/WS — *not* arbitrary inbound UDP.
FastRTC's WebRTC widget needs peer-to-peer media, so without a TURN relay
the browser can never reach the container's media socket and ICE
negotiation hangs at "Connecting…".

`fetch_acs_turn_config()` mints a short-lived ICE-server bundle from an
Azure Communication Services resource (Network Traversal API) so both the
browser and the server-side aiortc PeerConnection bounce media through
the TURN relay over outbound 443. Credentials are Entra-ID minted via the
container's managed identity (no connection strings).

On localhost (no ACS env vars set), this returns ``None`` and FastRTC
falls back to direct WebRTC, which works fine between a browser and a
local server.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from azure.communication.networktraversal.aio import CommunicationRelayClient
from azure.identity.aio import (
    ChainedTokenCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
)

_log = logging.getLogger("voice-live-demo.rtc")


def _credential() -> ChainedTokenCredential:
    """Mirror config.py's auth pattern: UAMI in ACA, AzCLI / azd locally."""
    client_id = os.environ.get("AZURE_CLIENT_ID")
    mi = (
        ManagedIdentityCredential(client_id=client_id)
        if client_id
        else ManagedIdentityCredential()
    )
    return ChainedTokenCredential(
        mi,
        DefaultAzureCredential(exclude_managed_identity_credential=True),
    )


async def fetch_acs_turn_config() -> dict[str, Any] | None:
    """Mint TURN ICE-server config from Azure Communication Services.

    Returns the FastRTC-compatible dict
    ``{"iceServers": [{"urls": [...], "username": "...", "credential": "..."}]}``
    on success, ``None`` otherwise (no ACS env var, no credential, transient
    failure — caller falls back to direct WebRTC).
    """
    endpoint = os.environ.get("ACS_ENDPOINT", "").strip()
    if not endpoint:
        _log.info(
            "ACS_ENDPOINT not set — using direct WebRTC. "
            "Works on localhost; on Azure Container Apps the browser will "
            "not be able to reach the container's media socket without TURN."
        )
        return None

    cred = _credential()
    try:
        async with CommunicationRelayClient(endpoint, cred) as relay:  # type: ignore[arg-type]
            cfg = await relay.get_relay_configuration()
    except Exception:
        _log.exception(
            "Failed to mint ACS TURN credentials from %s — "
            "falling back to direct WebRTC (will fail on remote browsers).",
            endpoint,
        )
        return None
    finally:
        try:
            await cred.close()
        except Exception:
            pass

    ice_servers = [
        {
            "urls": list(server.urls),
            "username": server.username,
            "credential": server.credential,
        }
        for server in cfg.ice_servers
    ]
    _log.info(
        "Minted ACS TURN config: %d ICE servers (expires %s).",
        len(ice_servers),
        cfg.expires_on.isoformat() if cfg.expires_on else "unknown",
    )
    return {"iceServers": ice_servers}
