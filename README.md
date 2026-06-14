# deepline-gtm-agent

Open-source GTM chat agent powered by [Deepline](https://deepline.com). The default path is Deepline v2 native agent/chat: your app brokers Slack, REST, and web chat requests while Deepline handles tool routing, enrichment, research, CRM actions, and provider-specific workflows through the v2 API.

**API portal:** [code.deepline.com](https://code.deepline.com) - create your `DEEPLINE_API_KEY` there.

## Quickstart

```bash
cd managed_agent
pip install -r requirements.txt

export DEEPLINE_API_KEY=dlp_...

python server.py     # starts REST, web chat, and Slack endpoints on :8000
```

Open `http://localhost:8000` for web chat, or call the REST API:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "find emails for 5 VP Sales at fintech companies"}'
```

## What it does

The agent handles common GTM workflows with Deepline's v2 tool catalog and API:

| Workflow | Example prompt |
|---|---|
| Contact enrichment | "Find the email for Jane Smith at Acme" |
| Prospect search | "Find 10 VP Sales at B2B SaaS companies, 200-500 employees, US" |
| Account research | "Research stripe.com and summarize GTM-relevant signals" |
| Email verification | "Is jsmith@acme.com safe to send?" |
| LinkedIn resolution | "Find the LinkedIn URL for Tom Nguyen at Notion" |
| CRM and outreach | "Create a HubSpot contact" or "show my Lemlist campaigns" |

Responses should include sources, provider outcomes, and a clear next step. The agent should state data gaps instead of inventing missing emails, titles, or company facts.

## GTM Agent Build Kit

This repo also includes the build-kit version of the Deepline x Exa GTM + AI talks:

- LangChain pattern: approval loops and traceable reasoning
- Exa pattern: search as workflow-ready context, not a link dump
- Composio pattern: scoped tools, auth boundaries, and controlled execution
- AssemblyAI pattern: conversation context before action
- Deepline pattern: source, verify, enrich, approve, write back, learn

Start here:

- [docs/gtm-agent-build-kit.md](docs/gtm-agent-build-kit.md) — short guide, prompts, and API examples
- [docs/notion-gtm-agent-field-guide.md](docs/notion-gtm-agent-field-guide.md) — long Notion-ready field guide with speaker learnings

The practical loop:

```
source -> verify -> bound tools -> draft/recommend -> approve -> write back -> learn
```

For build-agent, CRM writeback, outreach, voice/call, and bulk-list requests, the broker injects this operating loop before calling Deepline native chat.

## Architecture

```
Slack / REST / Web UI
      |
      v
FastAPI broker
      |
      v
Deepline v2 agent/chat + SDK/API
      |
      v
Deepline integrations, enrichment providers, CRM, outreach, and research tools
```

Configure access with environment variables and call the Deepline v2 SDK/API directly. Managed sessions should not depend on local Deepline CLI state.

## Interfaces

### Web chat

Run `python managed_agent/server.py` and open `http://localhost:8000`.

### REST

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Research rippling.com"}'
```

With endpoint protection enabled:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find 3 VP Sales in the US"}'
```

### Slack

Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`, then DM the bot or mention it in a channel. See [SETUP.md](SETUP.md).

### SDK/API

Use `DEEPLINE_API_KEY` for Deepline v2 API calls. Keep API keys in environment variables or your deployment secret store.

```python
import os
import httpx

resp = httpx.post(
    "https://code.deepline.com/api/v2/integrations/apollo_search_people/execute",
    headers={"Authorization": f"Bearer {os.environ['DEEPLINE_API_KEY']}"},
    json={"payload": {"job_title": "VP Sales", "limit": 5}},
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
```

For full chat behavior, use the v2 agent/chat SDK or API from the broker layer instead of shelling out to local CLI state.

## Deploy

See [SETUP.md](SETUP.md) for Railway and Slack setup. Required production variables:

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | Deepline v2 API key |
| `PORT` | Yes | Usually `8000` |
| `API_KEY` | Optional | Protects `/chat` endpoints with bearer auth |
| `CORS_ORIGINS` | Optional | Comma-separated allowed origins |
| `SLACK_BOT_TOKEN` | For Slack | Slack bot token |
| `SLACK_SIGNING_SECRET` | For Slack | Slack request signing secret |
| `REDIS_URL` | Optional | Persistent Slack thread history |

`ANTHROPIC_API_KEY`, `MANAGED_AGENT_ID`, and `MANAGED_ENVIRONMENT_ID` are only needed for the optional Anthropic Managed Agent shell in `managed_agent/setup.py`; they are not required for the default native Deepline v2 broker.

## Legacy self-hosted agent

The root Python package contains a legacy self-hosted agent path for local experimentation. It is not the recommended deployment path. New deployments should use the v2 native agent/chat flow above.

## License

MIT
