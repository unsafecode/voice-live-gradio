# AGENTS.md — guidance for AI coding agents working on this repo

This is a **public** repository (`unsafecode/voice-live-gradio`). It exists
to demonstrate to anyone in the world how trivially you can switch from
Azure OpenAI Realtime to Azure AI Foundry Voice Live. Everything in
`main` is publicly visible.

## Public-repo discipline

When making changes, **never commit**:

| Class | Examples | Where it should live instead |
|---|---|---|
| Customer / prospect names | company names, employee names, deal codes | nowhere in tracked files (chat / notes only) |
| Tenant / subscription IDs | GUIDs, subscription friendly names like `acme-prod` | nowhere; the repo is environment-agnostic |
| Specific resource names | concrete Foundry resource names, RG names, agent IDs | `.env` (gitignored) — `.env.example` keeps `<your-…>` placeholders only |
| API keys, tokens, connection strings | anything starting with `sk-`, `Bearer …`, or matching a key regex | nowhere ever — the repo is keyless by design (`ChainedTokenCredential`) |
| Internal team URLs / project shorthands | wiki links, deal-room URLs, internal Teams links | nowhere in tracked files |

Before every commit:

```bash
git diff --cached | grep -iE 'unipol|<customer>|<tenant-guid>|<sub-name>' || echo ok
```

(Substitute the names relevant to the in-flight engagement; obviously
don't commit the grep pattern with the real name in it either.)

## Architecture rules

- **The three rungs are the product.** `voicelive_demo/rungs/{realtime,voicelive,agent}.py`
  must stay tiny and read top-to-bottom. Anything reusable belongs one
  directory up.
- **The Switch diff tab reads the rung files live.** Don't add noise to
  the rungs (long comments, stylistic flourishes, dead imports) — every
  line shows up in the customer-facing diff. Keep them surgical.
- **All UI strings go through `i18n.py`.** Never hardcode a user-facing
  string in `ui.py` if it can be looked up in `STRINGS[locale]`. Adding
  a string = add the English key, the Italian key, and use
  `t["new_key"]` at the call site. Same for status labels, voice
  picker options, and diff card copy.
- **Auth is Entra ID only.** Don't add a code path that reads
  `*_API_KEY`. If a new Foundry service requires a token, extend the
  `ChainedTokenCredential` indirection in `config.py`.
- **No customer-specific personas.** The default system instructions in
  `i18n.py` (`DEFAULT_INSTRUCTIONS[locale]`) must stay neutral
  ("friendly, concise voice assistant"). Customer-specific prompt
  engineering lives in `.env` overrides or in a fork.

## Working in this repo (for coding agents)

- Smoke-test imports of all four shells before claiming done:
  ```bash
  for m in app_realtime app_voicelive app_agent app_demo; do
    .venv/bin/python -c "import $m; print('$m ok')"
  done
  ```
- Server is run with `uv run app.py` on port 7860. To restart cleanly:
  ```bash
  PID=$(lsof -tiTCP:7860 -sTCP:LISTEN) && [ -n "$PID" ] && kill $PID
  sleep 3
  nohup .venv/bin/python app.py > /tmp/voicelive-ui.log 2>&1 &
  ```
- Visual verification: Playwright shots at 1320×1400 in both `light`
  and `dark` color schemes. The hero, the rung-switch state, the
  language switcher, and the Switch diff tab are the four flows worth
  capturing.
- Changes to `STRINGS` must be applied to **both** locale dicts.
  Missing-key fallback is "use English silently" — which is the worst
  failure mode because customer-facing copy looks half-translated.
- When in doubt about a customer-facing string's tone, default to:
  short, neutral, technically accurate, no marketing fluff. The audience
  is engineering buyers evaluating the SDK delta.

## Branching

- `main` is what customers see when they click the repo. Never push
  work-in-progress to it.
- Feature branches: `feat/<short-name>`. Long-running refactors get
  their own branch and a draft PR.
- Commit messages: imperative mood, scope prefix
  (`feat(i18n):`, `fix(ui):`, `docs:`, etc.), Co-authored-by Copilot
  trailer when AI-assisted.
