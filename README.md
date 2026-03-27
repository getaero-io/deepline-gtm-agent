# deepline-gtm-agent

GTM automation agent powered by [Deepline](https://deepline.com) + [Deep Agents](https://github.com/langchain-ai/deepagents).

30+ enrichment and outreach providers. Slack bot. REST API. Zero boilerplate.

**Live demo:** https://deepline-gtm-agent-production.up.railway.app

---

## What it does

- **Enrich contacts** — work email, phone, job title from LinkedIn URL or name + company
- **Search prospects** — people matching ICP criteria (title, level, company size, geo)
- **Research accounts** — firmographics, tech stack, funding, headcount signals
- **Verify emails** — deliverability check before any send
- **Find LinkedIn URLs** — name + company → profile URL
- **Build company lists** — TAM discovery by industry, location, headcount

Every response includes a **Sources & Confidence** section showing which providers were called, what came back verified vs. missing, and the recommended next step.

---

## Interfaces

### 1. Slack bot

DM the bot or @-mention it in any channel. Replies in-thread, maintains conversation history per thread.

```
@Deepline GTM Agent find 5 VP of Sales at B2B SaaS, 200–500 employees, US
```

→ See [Slack setup](#slack-setup) below.

### 2. Chat UI

Open `chat.html` in any browser. Pre-loaded with 6 workflow templates.

### 3. REST API

```bash
# Single-turn
curl -X POST https://deepline-gtm-agent-production.up.railway.app/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Research rippling.com"}]}'

# Streaming SSE
curl -X POST https://deepline-gtm-agent-production.up.railway.app/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Find 3 VP of Sales in the US"}]}'
```

### 4. Python library

```python
from deepline_gtm_agent import create_gtm_agent

agent = create_gtm_agent()
result = agent.invoke({"messages": [{"role": "user", "content": "Research rippling.com"}]})
print(result["messages"][-1].content)
```

---

## Quickstart (self-hosted)

**Requirements:**
- Python 3.11+
- `DEEPLINE_API_KEY` — from [code.deepline.com](https://code.deepline.com)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

```bash
git clone https://github.com/jptoor/deepline-gtm-agent
cd deepline-gtm-agent
pip install ".[server]"

DEEPLINE_API_KEY=... OPENAI_API_KEY=... LLM_MODEL=openai:gpt-4o python server.py
```

Server runs on `http://localhost:8000`. Open `chat.html` to use it.

---

## Deploy to Railway

```bash
railway login
railway init
railway variables set DEEPLINE_API_KEY=... OPENAI_API_KEY=... LLM_MODEL=openai:gpt-4o PORT=8000
railway up --detach
railway domain
```

---

## Slack setup

**1.** Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch

**2.** OAuth & Permissions → Bot Token Scopes:
- `chat:write`
- `im:read` + `im:history`
- `app_mentions:read`
- `channels:read`

**3.** Install to workspace → copy **Bot User OAuth Token** (`xoxb-...`)

**4.** Basic Information → App Credentials → copy **Signing Secret**

**5.** Event Subscriptions → Enable → Request URL:
```
https://<your-railway-domain>/slack/events
```
Slack will verify immediately. Then subscribe to bot events: `app_mention`, `message.im`

**6.** Set env vars:
```bash
railway variables set SLACK_BOT_TOKEN=xoxb-... SLACK_SIGNING_SECRET=...
```

**Security:** every request is verified with HMAC-SHA256 against your signing secret. Requests older than 5 minutes are rejected to prevent replay attacks.

---

## Example prompts

See [`examples.md`](examples.md) for copy-paste ready prompts covering:

1. Inbound lead processing
2. Prospect discovery + enrichment
3. Account intelligence briefs
4. Competitive signal scoring
5. Email personalization at scale
6. Bulk email verification

---

## Tools

| Tool | Providers | Cost |
|------|-----------|------|
| `search_prospects` | Apollo `search_people_with_match` | ~0.17 credits/result |
| `enrich_person` | Apollo → Hunter → Crustdata | ~0.17 credits/match |
| `research_company` | Apollo → Crustdata | ~0.17 credits/call |
| `verify_email` | LeadMagic → ZeroBounce | free–low |
| `find_linkedin` | Apollo | free |
| `search_companies` | Apollo | ~0.17 credits/call |

---

## Swap the model

```python
agent = create_gtm_agent(model="openai:gpt-4o")
agent = create_gtm_agent(model="anthropic:claude-opus-4-6")
agent = create_gtm_agent(model="google:gemini-2.0-flash")
```

Or set `LLM_MODEL` env var on the server.

## Add your own tools

```python
def check_crm(email: str) -> dict:
    """Check if a contact already exists in HubSpot."""
    ...

agent = create_gtm_agent(extra_tools=[check_crm])
```

---

## Architecture

```
Slack DM / @mention
HTTP POST /chat
chat.html
        │
        ▼
    FastAPI server (server.py)
        │  Slack: verifies signature, replies async in-thread
        │  HTTP:  streams or returns full response
        ▼
    create_gtm_agent()       ← Deep Agents (LangGraph)
        │  model: gpt-4o / claude-opus-4-6
        │  system_prompt: GTM_SYSTEM_PROMPT
        │  tools: [search_prospects, enrich_person, ...]
        ▼
    deepline_execute(operation, payload)
        │  calls Deepline HTTP API directly
        ▼
    code.deepline.com  →  30+ providers
    (Apollo, Crustdata, Hunter, LeadMagic, ZeroBounce, ...)
```

---

## License

MIT
