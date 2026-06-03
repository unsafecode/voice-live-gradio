"""One-shot provisioner for the optional Foundry Agent rung.

Run this **once per Foundry project** to create the grounded support
agent that rung 3 (`MODE=agent`) connects to:

    uv sync --group provision
    uv run python -m voicelive_demo.provision_agent

What it does, in order:

1. Uploads every `docs/agent-kb/*.md` file to the Foundry project's
   OpenAI-compatible file store.
2. Creates a fresh vector store and ingests the uploaded files
   (waits for ingestion to finish).
3. Creates a new version of the Foundry Prompt Agent named
   ``voice-live-grounded-support`` with the persona from
   ``voicelive_demo/agent_persona.py`` and a ``file_search`` tool
   pointed at the vector store.
4. Prints the exact ``.env`` snippet to paste so rung 3 picks it up.

Auth is `DefaultAzureCredential` — sign in with ``az login`` first.
The signed-in identity needs **Foundry User** on the AI Services
account (role GUID ``53ca6127-db72-4b80-b1b0-d745d6d5456d``).

Inputs are taken from `.env` first, then CLI overrides. See ``--help``.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from azure.identity import DefaultAzureCredential

from voicelive_demo.agent_persona import AGENT_NAME, INSTRUCTIONS
from voicelive_demo.config import get_settings

KB_DIR = Path(__file__).resolve().parent.parent / "docs" / "agent-kb"


def _derive_project_endpoint(voice_live_endpoint: str, project_name: str) -> str:
    """Translate ``wss://<r>.services.ai.azure.com/voice-live`` to the
    HTTPS Foundry project endpoint expected by ``AIProjectClient``.
    """
    parsed = urlsplit(voice_live_endpoint)
    host = parsed.hostname
    if not host or not host.endswith(".services.ai.azure.com"):
        raise SystemExit(
            "AZURE_VOICELIVE_ENDPOINT must be a wss:// URL on "
            "*.services.ai.azure.com; got: " + voice_live_endpoint
        )
    return f"https://{host}/api/projects/{project_name}"


def _kb_files() -> list[Path]:
    files = sorted(p for p in KB_DIR.glob("*.md") if p.is_file())
    if not files:
        raise SystemExit(f"No markdown files found in {KB_DIR}")
    return files


def _upload_files(openai_client, files: Iterable[Path]) -> list[str]:
    file_ids: list[str] = []
    for path in files:
        with path.open("rb") as fh:
            uploaded = openai_client.files.create(file=fh, purpose="assistants")
        print(f"  uploaded {path.name} → {uploaded.id}")
        file_ids.append(uploaded.id)
    return file_ids


def _ingest(openai_client, vector_store_id: str, file_ids: list[str]) -> None:
    batch = openai_client.vector_stores.file_batches.create_and_poll(
        vector_store_id=vector_store_id,
        file_ids=file_ids,
    )
    if batch.status != "completed":
        raise SystemExit(
            f"Vector store ingestion did not complete: status={batch.status} "
            f"(counts={batch.file_counts!r})"
        )
    print(
        f"  ingested {batch.file_counts.completed}/{batch.file_counts.total} "
        f"files into {vector_store_id}"
    )


def provision(*, project_endpoint: str, model: str, agent_name: str) -> str:
    try:
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import FileSearchTool, PromptAgentDefinition
    except ImportError as exc:
        raise SystemExit(
            "azure-ai-projects is not installed. Run:\n"
            "    uv sync --group provision\n"
        ) from exc

    print(f"→ Connecting to {project_endpoint}")
    project = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
    )
    openai_client = project.get_openai_client()

    files = _kb_files()
    print(f"→ Uploading {len(files)} knowledge-base files")
    file_ids = _upload_files(openai_client, files)

    print("→ Creating vector store and ingesting files")
    vector_store = openai_client.vector_stores.create(name=f"{agent_name}-kb")
    _ingest(openai_client, vector_store.id, file_ids)

    print(f"→ Creating Foundry Prompt Agent: {agent_name} (model={model})")
    agent = project.agents.create_version(
        agent_name=agent_name,
        definition=PromptAgentDefinition(
            model=model,
            instructions=INSTRUCTIONS,
            tools=[FileSearchTool(vector_store_ids=[vector_store.id])],
        ),
    )
    print(f"  agent={agent.name} version={agent.version}")
    return agent.name


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--project-name",
        help="Foundry project name. Defaults to AGENT_PROJECT_NAME in .env.",
    )
    parser.add_argument(
        "--project-endpoint",
        help=(
            "Full HTTPS project endpoint, e.g. "
            "https://<resource>.services.ai.azure.com/api/projects/<project>. "
            "Defaults to derive from AZURE_VOICELIVE_ENDPOINT + project name."
        ),
    )
    parser.add_argument(
        "--model",
        help=(
            "Chat-completion model deployment that backs the agent. "
            "Defaults to AGENT_MODEL in .env (which itself defaults to "
            "gpt-4.1-mini). Distinct from the realtime model in "
            "AZURE_OPENAI_DEPLOYMENT_NAME — Voice Live wraps STT/TTS "
            "around this reasoning model."
        ),
    )
    parser.add_argument(
        "--agent-name",
        default=AGENT_NAME,
        help=f"Agent name (immutable). Defaults to {AGENT_NAME!r}.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()

    project_name = args.project_name or settings.agent_project_name
    if not project_name:
        print(
            "Foundry project name is required. Pass --project-name "
            "or set AGENT_PROJECT_NAME in .env.",
            file=sys.stderr,
        )
        return 2

    project_endpoint = args.project_endpoint or _derive_project_endpoint(
        settings.azure_voice_live_endpoint, project_name
    )
    model = args.model or settings.agent_model

    agent_name = provision(
        project_endpoint=project_endpoint,
        model=model,
        agent_name=args.agent_name,
    )

    print()
    print("✅ Done. Paste the following into your .env to enable rung 3:")
    print()
    print(f"AGENT_PROJECT_NAME={project_name}")
    print(f"AGENT_ID={agent_name}")
    print()
    print("Then run:  MODE=agent uv run app.py  (or MODE=demo to switch rungs in-UI)")

    # azure-identity opens an aiohttp session in its sync path on some
    # versions; explicitly close to avoid an unclosed-session warning.
    try:
        asyncio.get_event_loop().close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
