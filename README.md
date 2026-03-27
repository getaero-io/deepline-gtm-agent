# deepline-gtm-agent

Open-source GTM agent built on [Deepline](https://deepline.com) + [Deep Agents](https://github.com/langchain-ai/deepagents) (LangChain).

This is a reference implementation — a working starter kit you can deploy as-is or fork and extend. Deepline handles the data layer (30+ enrichment and outreach providers). Deep Agents handles the orchestration (LangGraph-powered agent loop). You write the business logic.

**API portal:** [code.deepline.com](https://code.deepline.com) — get your `DEEPLINE_API_KEY` here
**GitHub:** [github.com/jptoor/deepline-gtm-agent](https://github.com/jptoor/deepline-gtm-agent)
**Live demo:** [deepline-gtm-agent-production.up.railway.app](https://deepline-gtm-agent-production.up.railway.app)

---

## What it does

- **Enrich contacts** — work email, phone, job title from a LinkedIn URL or name + company
- **Search prospects** — people matching ICP filters (title, seniority, company size, geo)
- **Research accounts** — firmographics, tech stack, funding, headcount signals
- **Verify emails** — deliverability check before any send
- **Find LinkedIn URLs** — name + company → profile URL
- **Build company lists** — TAM discovery by industry, location, headcount

Every response includes a **Sources & Confidence** section: which providers ran, what came back verified vs. missing, and a recommended next step. The agent is honest about data gaps — it won't paper over obfuscated last names or unverified emails.

---

## How it works

```
Your query
    │
    ▼
Deep Agents (LangGraph)          ← orchestration, tool-calling, conversation memory
    │  model: gpt-4o / claude / gemini
    │  tools: search_prospects, enrich_person, verify_email, ...
    ▼
Deepline API (code.deepline.com) ← single key, 30+ providers underneath
    │
    ├── Apollo      (270M people, prospect search, enrichment)
    ├── Hunter      (domain-level email patterns)
    ├── Crustdata   (LinkedIn-native, headcount signals)
    ├── LeadMagic   (email verification)
    ├── ZeroBounce  (email verification)
    └── ... 25+ more
```

You don't manage individual provider keys or handle fallback logic — Deepline does that. One API key, one bill, one place to add providers.

---

## Quickstart

You need:
- Python 3.11+
- `DEEPLINE_API_KEY` from [code.deepline.com](https://code.deepline.com)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

```bash
git clone https://github.com/jptoor/deepline-gtm-agent
cd deepline-gtm-agent
pip install ".[server]"

export DEEPLINE_API_KEY=...
export OPENAI_API_KEY=...
export LLM_MODEL=openai:gpt-4o

python server.py
```

Server starts on `http://localhost:8000`. Open `chat.html` to use it.

Try it immediately without the UI:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Research rippling.com"}]}'
```

---

## Interfaces

### Slack bot

DM the bot or @-mention it in any channel. Replies in-thread, maintains conversation history per thread.

```
@Deepline GTM Agent find 5 VP of Sales at B2B SaaS, 200–500 employees, US
```

→ See [Slack setup](#slack-setup) below.

### Chat UI

Open `chat.html` in any browser. Pre-loaded with 6 workflow templates.

### REST API

```bash
# Single-turn
curl -X POST https://deepline-gtm-agent-production.up.railway.app/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Enrich jane@acme.com"}]}'

# Streaming SSE
curl -X POST https://deepline-gtm-agent-production.up.railway.app/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Find 3 VP of Sales in the US"}]}'
```

### Python

```python
from deepline_gtm_agent import create_gtm_agent

agent = create_gtm_agent()
result = agent.invoke({"messages": [{"role": "user", "content": "Research rippling.com"}]})
print(result["messages"][-1].content)
```

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

**1.** [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch

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
Slack verifies immediately. Subscribe to: `app_mention`, `message.im`

**6.** Set env vars:
```bash
railway variables set SLACK_BOT_TOKEN=xoxb-... SLACK_SIGNING_SECRET=...
```

Every request is verified with HMAC-SHA256. Requests older than 5 minutes are rejected.

---

## Customization

### Swap the model

```python
agent = create_gtm_agent(model="openai:gpt-4o")
agent = create_gtm_agent(model="anthropic:claude-opus-4-6")
agent = create_gtm_agent(model="google:gemini-2.0-flash")
```

Or set `LLM_MODEL` as an env var.

### Add your own tools

```python
def check_crm(email: str) -> dict:
    """Check if a contact already exists in HubSpot."""
    ...

agent = create_gtm_agent(extra_tools=[check_crm])
```

---

## Tools

| Tool | Providers | Cost |
|------|-----------|------|
| `search_prospects` | Apollo | ~0.17 credits/result |
| `enrich_person` | Apollo → Hunter → Crustdata | ~0.17 credits/match |
| `research_company` | Apollo → Crustdata | ~0.17 credits/call |
| `verify_email` | LeadMagic → ZeroBounce | free–low |
| `find_linkedin` | Apollo | free |
| `search_companies` | Apollo | ~0.17 credits/call |

---

## Example prompts

See [`examples.md`](examples.md) for copy-paste prompts covering:

1. Inbound lead processing
2. Prospect discovery + enrichment
3. Account intelligence briefs
4. Competitive signal scoring
5. Email personalization at scale
6. Bulk email verification

---

## License

MIT
