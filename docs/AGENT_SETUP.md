# Setting up rung 3 — Voice Live + Foundry Agent

The first two rungs (`MODE=realtime` and `MODE=voicelive`) need nothing
more than a Foundry resource and a model deployment. The third rung
talks to a **hosted Foundry Prompt Agent**, so it needs an agent to
exist on the Azure side first. This page is the 5-minute path to
creating one.

The agent demoes the same shape a real customer would ship: a friendly
voice assistant grounded with **file_search** over a small fictional
knowledge base (`docs/agent-kb/*.md`). The runtime code is unchanged —
the rung still reads:

```python
extra_query={
    "agent-id":           settings.agent_id,
    "agent-project-name": settings.agent_project_name,
    "agent-access-token": await azure_agent_token_provider(),
}
```

…all that's new is two `.env` values pointing at the agent you create
here.

## Prerequisites

You should already have followed [`docs/PEER_SETUP.md`](PEER_SETUP.md):

- A Foundry resource (AI Services account) and project in your sub.
- A realtime-capable model deployed in that resource
  (`gpt-realtime`, `gpt-realtime-1.5`, `gpt-realtime-2`, …).
- Your `.env` populated with `AZURE_OPENAI_ENDPOINT` and
  `AZURE_VOICELIVE_ENDPOINT`.
- `az login` against the subscription that owns the resource.

You will also need:

- The **Foundry User** role on the AI Services account
  (role GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d`). This is the same
  role Voice Live already needs for rung 2 — usually nothing new to
  assign.
- The **Foundry project name** (not the resource name). You can find
  it in *ai.azure.com → your hub → your project*.

## Provision the agent

From the repo root:

```bash
# Install the provisioning-only deps (kept out of the runtime app):
uv sync --group provision

# Run the one-shot provisioner. Most defaults come from .env.
uv run python -m voicelive_demo.provision_agent --project-name <your-foundry-project>
```

The script will:

1. Upload every file in `docs/agent-kb/*.md` to the project's file store.
2. Create a vector store called `voice-live-grounded-support-kb` and
   wait for ingestion to finish.
3. Create (or version-bump) a Foundry Prompt Agent called
   `voice-live-grounded-support` with the persona from
   `voicelive_demo/agent_persona.py` and a `file_search` tool over the
   vector store.

When it finishes, you'll see:

```
✅ Done. Paste the following into your .env to enable rung 3:

AGENT_PROJECT_NAME=<your-foundry-project>
AGENT_ID=voice-live-grounded-support
```

Paste those two lines into your `.env` and restart the app.

## Try it

```bash
MODE=demo uv run app.py        # switch rungs from the UI
# – or, locked to rung 3 –
MODE=agent uv run app.py
```

Pick **Foundry Agent** in the switcher, then ask a knowledge-base
question, e.g.:

- *"What's the Enterprise plan's first-response SLA on a Severity-1?"*
- *"How long do you keep my logs on the Pro plan?"*
- *"What does a 429 mean and what's my rate limit?"*

The agent should answer from the knowledge base (and only the KB —
when you ask something outside it, it should offer to open a ticket
instead of inventing a number).

## Re-running the provisioner

The script is safe to re-run. Foundry Prompt Agent versions are
**immutable**, so each run creates a new version under the same
`voice-live-grounded-support` name. Rung 3 always picks up the latest
published version, so you usually do not need to change `.env` after
a re-provision.

Each run **does** create a new vector store and uploads fresh file
copies. They are cheap, but if you re-run frequently, periodically
clean up unused vector stores from the Foundry portal.

## Customising the persona or knowledge base

- **Persona** — edit `voicelive_demo/agent_persona.py` (the
  `INSTRUCTIONS` string), then re-run the provisioner. The new version
  is live immediately.
- **Knowledge base** — drop or replace markdown files in
  `docs/agent-kb/`, then re-run the provisioner.
- **Other tools** — `PromptAgentDefinition` also supports
  `WebSearchTool`, `CodeInterpreterTool`, `MCPTool`, `OpenApiTool`,
  `AzureAISearchTool`, and `BingGroundingTool`. Add them to the
  `tools=[…]` list in `provision_agent.py`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `azure-ai-projects is not installed` | Run `uv sync --group provision`. |
| `401` / `403` on `create_version` | The signed-in identity needs **Foundry User** on the AI Services account (not just the project). Use `az role assignment create --assignee <upn> --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope <ai-services-resource-id>`. |
| `Model not found` | The model name you passed (or `AZURE_OPENAI_DEPLOYMENT_NAME`) is not deployed in the Foundry project. Deploy it from *ai.azure.com → Models + endpoints*. |
| `The project does not exist` | Check the project name spelling, or pass `--project-endpoint` explicitly: `https://<resource>.services.ai.azure.com/api/projects/<project>`. |
| Vector store ingestion times out | Knowledge-base files larger than a few MB take a minute or two. Re-run; the SDK will poll again. |
| Agent answers but ignores the KB | Make sure your question is about Contoso Cloud (the fictional company the persona is grounded on). Generic questions outside the KB are answered without `file_search`. |

## Tearing down

Removing the rung 3 setup is two clicks in the Foundry portal:

1. Delete the `voice-live-grounded-support` agent.
2. Delete its vector store (look for one suffixed `…-kb`).

Then clear `AGENT_ID` and `AGENT_PROJECT_NAME` from `.env`. The rung
3 button auto-hides from the UI when those values are empty.
