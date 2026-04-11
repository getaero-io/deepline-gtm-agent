# Deepline GTM Agent — Managed Agent Edition

Runs the Deepline GTM agent entirely inside [Anthropic Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview). No LangGraph, no local tool execution. The `deepline` CLI + auth + skill docs are uploaded into each session's sandbox.

## How it works

```
You (Slack / REST / Web UI)
  │
  ▼
FastAPI server (this code)
  │
  ├─ creates Managed Agent session via Anthropic API
  ├─ uploads: deepline binary + auth + skill docs
  ├─ sends your message
  └─ streams events back to you
       │
       ▼
  Anthropic sandbox container
    ├─ deepline CLI installed + authenticated
    ├─ bash, read, write, edit, glob, grep, web_fetch, web_search
    └─ full access to code.deepline.com (441+ tools)
```

## Setup

```bash
pip install -r requirements.txt

# One-time: create the agent + environment on Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python setup.py
```

This creates `.agent_config.json` with your `agent_id` and `environment_id`.

## Run

### CLI
```bash
python cli.py "find 10 Series B fintech companies hiring GTM engineers"
python cli.py --eval email-waterfall
```

### Server (REST + Slack + Web UI)
```bash
python server.py
# Visit http://localhost:8000 for web chat
# POST /chat or /chat/stream for API access
```

### Docker
```bash
docker build -f managed_agent/Dockerfile -t deepline-managed-agent .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v ~/.local/bin/deepline:/usr/local/bin/deepline \
  -v ~/.local/deepline:/root/.local/deepline \
  -v ~/.claude/skills/gtm-meta-skill:/app/gtm-meta-skill \
  deepline-managed-agent
```

## Deploy to Railway

```bash
railway init
railway variables set ANTHROPIC_API_KEY=sk-ant-...
# Copy agent_id and environment_id from .agent_config.json
railway up --detach
```

## API

### POST /chat
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "find emails for 5 VP Sales at fintech companies"}'
```

### POST /chat/stream
```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "enrich leads.csv with work emails"}'
```

### Slack
Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`, then DM the bot or @mention it.

## Access patterns

| Interface | Best for | How |
|-----------|----------|-----|
| **Slack** | GTM teams, async enrichment | @mention bot or DM |
| **Web UI** | Exploration, CSV workflows | Visit `/` on your server |
| **REST API** | Programmatic access, cron | POST to `/chat` or `/chat/stream` |
| **CLI** | Evals, developer use | `python cli.py "..."` |

## vs. LangGraph edition

| | LangGraph (`/`) | Managed Agent (`/managed_agent`) |
|---|---|---|
| Agent loop | Your server (LangGraph) | Anthropic's infrastructure |
| Tool execution | Your server (Python) | Anthropic sandbox (bash) |
| Deepline access | HTTP client in-process | `deepline` CLI in sandbox |
| Scaling | You manage | Anthropic manages |
| Customization | Full control | System prompt + tools |
