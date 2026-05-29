# Deepline GTM Agent

FastAPI broker for Deepline v2 native agent/chat. It exposes REST, streaming, web chat, and Slack endpoints while Deepline handles GTM tool routing through the v2 SDK/API.

## How It Works

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
Deepline integrations and provider workflows
```

Configure the broker with environment variables. Managed sessions should not depend on local Deepline CLI state.

## Setup

```bash
pip install -r requirements.txt

export DEEPLINE_API_KEY=dlp_...

python server.py
```

Open `http://localhost:8000` for web chat.

### Docker
```bash
docker build -f managed_agent/Dockerfile -t deepline-managed-agent .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v ~/.local/bin/deepline:/usr/local/bin/deepline \
  -v ~/.local/deepline:/root/.local/deepline \
  -v ~/.claude/skills/deepline-gtm:/app/deepline-gtm \
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
  -d '{"message": "research stripe.com"}'
```

Set `API_KEY` to require `Authorization: Bearer <API_KEY>` on chat endpoints.

## Docker

```bash
docker build -f managed_agent/Dockerfile -t deepline-gtm-agent .
docker run -p 8000:8000 \
  -e DEEPLINE_API_KEY=dlp_... \
  deepline-gtm-agent
```

## Railway

```bash
railway init
railway variables set \
  DEEPLINE_API_KEY=dlp_... \
  PORT=8000
railway up --detach
```

For Slack, also set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`.

`ANTHROPIC_API_KEY`, `MANAGED_AGENT_ID`, and `MANAGED_ENVIRONMENT_ID` are optional and only used by `setup.py` / `session.py` for manual Anthropic Managed Agent experiments. The default broker path does not require them.

## Environment

See [env.example](env.example) for all supported variables.
