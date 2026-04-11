# deepline-gtm-agent

Open-source GTM agent powered by [Deepline](https://deepline.com) (441+ data integrations) with two deployment options:

| | **Managed Agent** (recommended) | **LangGraph** |
|---|---|---|
| Agent loop | [Anthropic Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) | [Deep Agents](https://github.com/langchain-ai/deepagents) (LangGraph) |
| Tool execution | Anthropic sandbox (`deepline` CLI) | Your server (Python) |
| Scaling | Anthropic manages | You manage |
| Model | Claude Opus 4.6 | Claude / GPT-4o / Gemini |
| Setup | `python setup.py` + deploy | `pip install` + deploy |
| Code | [`managed_agent/`](managed_agent/) | Root (`server.py`, `deepline_gtm_agent/`) |

**Managed Agent** is the default - Anthropic runs the agent loop and sandbox, your server is a thin broker. See [`managed_agent/README.md`](managed_agent/README.md) for full docs.

**LangGraph** is the self-hosted alternative - you run the agent loop and tool execution on your own infrastructure. Docs below.

**API portal:** [code.deepline.com](https://code.deepline.com) - get your `DEEPLINE_API_KEY` here

---

## Quickstart (Managed Agent)

```bash
pip install anthropic fastapi uvicorn httpx

export ANTHROPIC_API_KEY=sk-ant-...
export DEEPLINE_API_KEY=dlp_...

cd managed_agent
python setup.py          # one-time: creates agent + environment on Anthropic
python server.py         # starts server on :8000 (REST + Slack + Web UI)
```

Access it:
- **Web chat:** http://localhost:8000
- **REST:** `curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message": "find emails for 5 VP Sales at fintech companies"}'`
- **Slack:** set `SLACK_BOT_TOKEN` + `SLACK_SIGNING_SECRET`, DM or @mention the bot
- **CLI:** `python cli.py "research stripe.com"`

See [`managed_agent/README.md`](managed_agent/README.md) for deploy instructions (Railway, Docker).

---

## What it does

The agent handles core GTM workflows, each backed by a waterfall of data providers:

| Workflow | What you ask | What happens |
|---|---|---|
| **Enrich contacts** | "Find the email for Jane Smith at Acme" | 9-provider waterfall: Dropleads → Hunter → LeadMagic → Deepline Native → Crustdata → Icypeas → Prospeo → PDL → Forager |
| **Search prospects** | "Find 10 VP of Sales at B2B SaaS, 200–500 employees, US" | Dropleads (free, broad) → Icypeas (recently-hired filter) → Deepline Native (domain-specific) |
| **Research accounts** | "Research stripe.com" | Crustdata → Exa web; returns description, headcount, funding, tech stack, HQ |
| **Verify emails** | "Is jsmith@acme.com safe to send?" | LeadMagic → ZeroBounce; returns valid/invalid + MX provider + sub-status |
| **Find LinkedIn URLs** | "LinkedIn for Tom Nguyen at Notion" | Deepline Native Prospector → Exa web; returns URL + confidence level |
| **Build company lists** | "Find 25 fintech companies in NYC, 100–500 employees" | Apollo company search; returns name, domain, headcount, industry, description |
| **CRM read/write** | "Create a HubSpot contact for Jane Doe" | Full HubSpot, Salesforce, and Attio access via `deepline_call` |
| **Outreach** | "Show me my Lemlist campaigns" | Instantly, Lemlist, Smartlead, HeyReach — full campaign and lead management |

Every response includes a **Sources** section: which providers ran and a recommended next step. The agent is explicit about data gaps — it won't invent emails or paper over missing data.

---

## How it works

### Managed Agent (recommended)

```
Slack / REST / Web UI
      |
      v
FastAPI server (thin broker)     <-- creates sessions, streams results
      |
      v
Anthropic Managed Agents         <-- agent loop + sandboxed container
      |  model: Claude Opus 4.6
      |  tools: bash, read, write, edit, glob, grep, web_fetch, web_search
      |  + deepline CLI (authenticated, full access)
      |
      v
Deepline API (code.deepline.com) <-- 441+ integrations
```

The agent runs the `deepline` CLI inside Anthropic's sandbox. It reads skill docs, picks providers, runs waterfalls, handles retries - all autonomously. Your server just brokers the connection.

### LangGraph (self-hosted alternative)

```
Slack / REST / Web UI
      |
      v
FastAPI + LangGraph              <-- agent loop + tool execution on YOUR server
      |  model: claude-opus-4-6 / gpt-4o / gemini-2.0-flash
      |  8 high-level tools + deepline_call passthrough
      |
      v
Deepline API (code.deepline.com) <-- 441+ integrations
```

You run the agent loop. Tools execute in your Python process via the Deepline HTTP API. More control, more operational overhead.

---

## Quickstart (LangGraph)

For the self-hosted LangGraph version:

```bash
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

DM the bot or @-mention it in any channel. Replies in-thread, maintains conversation history per thread (Redis-backed with 7-day TTL, falls back to in-memory without Redis).

```
@Deepline GTM Agent find 5 VP of Sales at B2B SaaS, 200–500 employees, US
```

→ See [Slack setup](#deploy--slack-setup) below.

### Chat UI

Open `chat.html` in any browser. Pre-loaded with workflow templates.

### REST API

```bash
# Single-turn
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Enrich jane@acme.com"}]}'

# With API key (if API_KEY env var is set)
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Enrich jane@acme.com"}]}'

# Streaming SSE
curl -X POST http://localhost:8000/chat/stream \
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

## Tools

Nine tools are registered on the agent. The eight high-level tools handle common GTM workflows with built-in waterfalls. `deepline_call` is a passthrough to all 441+ Deepline integrations — CRM, outreach, scraping, and anything not covered by a dedicated tool.

### `waterfall_enrich`

**When to use:** You have any combination of name, LinkedIn URL, email, or company — and want the best possible email result without thinking about provider selection.

**Inputs:** At least one of `linkedin_url`, `email`, or `first_name + last_name`. Optionally `company_domain` or `company_name`.

**Waterfall (9 providers, stops on first hit):** Dropleads → Hunter → LeadMagic → Deepline Native → Crustdata → Icypeas → Prospeo → PeopleDataLabs → Forager

**Returns:** `{email, phone, linkedin_url, title, company, location, provider, providers_tried}`

**Use this over `enrich_person`** for bulk enrichment or when you want Deepline to handle provider selection automatically.

---

### `enrich_person`

**When to use:** You have a contact and need their work email, phone, or LinkedIn URL. Use when you want predictable provider routing.

**Inputs:** At least one of `linkedin_url`, `email`, or `first_name + last_name`. Optionally `company_domain` or `company_name`.

**Waterfall:** Hunter (domain + name) → Crustdata (LinkedIn URL) → Deepline Native Prospector (domain)

**Returns:** `{email, phone, title, company, linkedin_url, location, provider}`

**Limitations:** Fewer providers than `waterfall_enrich` — use `waterfall_enrich` for better coverage.

---

### `search_prospects`

**When to use:** You need a list of people matching ICP criteria (title, seniority, location, company size, industry).

**Inputs:** Any combination of `job_title`, `job_level`, `company_name`, `company_domain`, `person_location`, `company_size_min`, `company_size_max`, `company_industry`, `recently_hired_months`, `limit` (default 10, max 25).

`job_level` accepted values: `owner`, `founder`, `c_suite`, `vp`, `director`, `manager`, `individual_contributor`

`recently_hired_months`: filter to people who started their current role within this many months — routes to Icypeas which supports job start-date filtering.

`person_location`: accepts country names, US states, or major cities. Cities and states are automatically mapped to country-level for Dropleads; Icypeas accepts city-level directly.

**Waterfall:**
1. Icypeas (when `recently_hired_months` is set — supports job start-date filtering)
2. Dropleads (free, broad coverage, automatic title expansion for niche roles)
3. Deepline Native Prospector (when `company_domain` provided — returns verified emails)
4. Icypeas fallback (when Dropleads has no coverage)

**Returns:** `{prospects: [{name, title, company, linkedin_url, email, location, company_size, industry, has_email}], count, total, provider}`

**Limitations:** Dropleads filters by country only — city-level filtering falls back to Icypeas. Dropleads industry taxonomy is narrow — if 0 results are returned with an industry filter, the tool retries without it and notes the limitation.

---

### `research_company`

**When to use:** You need firmographic data on a company — headcount, funding, tech stack, description, HQ.

**Inputs:** `domain` (e.g. `"stripe.com"`) or `company_name`.

**Waterfall:** Crustdata (LinkedIn-native, headcount signals) → Exa web research (live, most current)

**Returns:** `{name, domain, description, industry, headcount, funding, location, linkedin_url, website, technologies, provider}`

**Limitations:** Crustdata data can be 6–18 months stale. The Exa fallback hits live web sources and is more current. If headcount signals matter, follow up with `web_research` for recent job postings.

---

### `web_research`

**When to use:** Anything requiring live web data — C-suite name lookups, recent news, funding rounds, job postings, product launches, anything not in structured databases.

**Inputs:** `query` — a plain-language research question or instruction.

**Provider:** Exa research (neural web search + content extraction)

**Returns:** `{summary, query, provider}` — structured narrative with citations

---

### `verify_email`

**When to use:** Before including an email in an outbound sequence. Always run this — a bounced email harms sender reputation.

**Inputs:** `email` (single address)

**Waterfall:** LeadMagic email_validation → ZeroBounce batch_validate (if LeadMagic returns unknown)

**Returns:** `{email, valid, status, safe_to_send, mx_provider, sub_status, provider}`

`safe_to_send` is `False` for valid addresses that are disposable or role-based (e.g. `info@`, `support@`).

Email status guide: `valid` = send • `catch_all` = use with caution • `invalid` = drop • `unknown` = unusable

---

### `find_linkedin`

**When to use:** You have a name + company and need the LinkedIn profile URL.

**Inputs:** `first_name`, `last_name` (required). `company_name` or `company_domain` (optional but strongly recommended to avoid false matches).

**Waterfall:** Deepline Native Prospector (if domain known, high confidence) → Exa web research (medium confidence)

**Returns:** `{linkedin_url, confidence, provider}` — `confidence` is `"high"`, `"medium"`, or `"none"`

**Limitations:** Without a company, the Exa path can return wrong people. Always pass `company_name` or `company_domain` when you have it.

---

### `search_companies`

**When to use:** Building a target account list before finding contacts. Also useful for TAM analysis.

**Inputs:** Any combination of `industry`, `location`, `headcount_min`, `headcount_max`, `keywords`, `limit` (default 25, max 25).

**Provider:** Apollo company search

**Returns:** `{companies: [{name, domain, headcount, industry, description, location}], count, provider}`

**Limitations:** Apollo keyword filtering is broad-match — results may include tangentially related companies. Use `research_company` or `web_research` to validate individual results.

---

### `deepline_call`

**When to use:** Anything not covered by the eight high-level tools above — CRM operations, outreach campaign management, LinkedIn scraping, ad intelligence, or any of the 441+ Deepline integrations.

**Inputs:** `tool_id` (string), `payload` (dict). The full tool catalog is embedded in the tool's description — the agent selects `tool_id` automatically based on the request.

**Examples of what this covers:**

| Request | tool_id |
|---|---|
| Read HubSpot contacts | `hubspot_search_objects` with `{"objectType": "contacts"}` |
| Create HubSpot deal | `hubspot_create_deal` |
| List Salesforce leads | `salesforce_list_leads` |
| Create Salesforce opportunity | `salesforce_create_opportunity` |
| Read Attio contacts | `attio_query_person_records` |
| List Lemlist campaigns | `lemlist_list_campaigns` |
| Check Lemlist replies | `lemlist_get_activities` with `{"type": "emailsReplied"}` |
| Add lead to Instantly | `instantly_add_to_campaign` |
| List HeyReach campaigns | `heyreach_list_campaigns` |
| Scrape a website | `firecrawl_scrape` |
| Look up tech stack | `builtwith_domain_lookup` |
| Search Google ads | `adyntel_google` |
| Run Apollo people search | `apollo_search_people` |
| Scrape LinkedIn profiles | `apify_run_actor` with a LinkedIn scraper actor |

---

## Deploy + Slack setup

See **[SETUP.md](SETUP.md)** for full instructions — CLI path (fast, scriptable) and UI path (step by step).

Quick version:

```bash
# Deploy to Railway
railway login && railway init
railway variables set DEEPLINE_API_KEY=... OPENAI_API_KEY=... LLM_MODEL=openai:gpt-4o PORT=8000
railway up --detach && railway domain

# After getting your Railway domain — set up Slack
# Edit slack-manifest.json, replace YOUR_RAILWAY_DOMAIN, then:
# api.slack.com/apps → Create New App → From manifest → paste it
# Install to workspace → copy xoxb- token + signing secret → set in Railway:
railway variables set SLACK_BOT_TOKEN=xoxb-... SLACK_SIGNING_SECRET=...
railway up --detach
```

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

Tools follow the Deep Agents convention: plain Python function, type-annotated parameters, clear docstring. The framework auto-generates the tool schema and registers it with the agent.

### Override the system prompt

```python
agent = create_gtm_agent(
    system_prompt="You are a MEDDIC qualification specialist. For every account..."
)
```

---

## Security notes

**Running locally:** The server is open by default — no API key, CORS allows all origins. This is intentional for local dev.

**Running in production:**

- **Protect the `/chat` endpoints** — set `API_KEY` env var. Clients must send `Authorization: Bearer <key>`.
- **Restrict CORS** — set `CORS_ORIGINS=https://your-app.com` (comma-separated for multiple origins). Defaults to `*`.
- **Slack signature verification** — already enforced. Every Slack request is verified with HMAC-SHA256 against your `SLACK_SIGNING_SECRET`. Requests older than 5 minutes are rejected.
- **Slack OAuth token** — the `/slack/oauth_redirect` endpoint displays the bot token in the browser so you can copy it into Railway. Treat this page like a password: access it once, copy the token, then don't revisit.
- **HTTPS** — required in production. Railway provides automatic TLS.

**Known limitations of this reference implementation:**

- **Slack conversation history** — Redis-backed when `REDIS_URL` is set (7-day TTL per thread). Without Redis, history falls back to in-memory and is lost on restart. Add a Redis plugin in Railway to enable persistence.
- **No rate limiting** — the `/chat` endpoints have no per-user or per-IP throttling. Add this at the reverse proxy layer or via FastAPI middleware if you expose the server publicly.
- **Single Slack workspace** — the OAuth flow exchanges a code for a bot token and asks you to set it manually. A multi-workspace distribution would store tokens per team in a database.

---

## Example prompts

See [`examples.md`](examples.md) for copy-paste prompts covering enrichment, prospecting, account research, CRM operations, outreach management, and email verification.

---

## License

MIT
