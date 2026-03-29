# deepline-gtm-agent

Open-source GTM agent built on [Deepline](https://deepline.com) + [Deep Agents](https://github.com/langchain-ai/deepagents) (LangGraph).

This is a reference implementation — a working starter kit you can deploy as-is or fork and extend. Deepline handles the data layer (30+ enrichment and outreach providers). Deep Agents handles the orchestration (LangGraph-powered agent loop). You write the business logic.

Inspired by ["How we built LangChain's GTM Agent"](https://blog.langchain.com/how-we-built-langchains-gtm-agent/) — this repo is the Deepline-powered version of that architecture, deployable in minutes.

**API portal:** [code.deepline.com](https://code.deepline.com) — get your `DEEPLINE_API_KEY` here
**GitHub:** [github.com/jptoor/deepline-gtm-agent](https://github.com/jptoor/deepline-gtm-agent)

---

## What it does

The agent handles six core GTM workflows, each backed by a waterfall of data providers:

| Workflow | What you ask | What happens |
|---|---|---|
| **Enrich contacts** | "Find the email for Jane Smith at Acme" | Apollo → Hunter → Crustdata waterfall; returns verified email, phone, title, LinkedIn |
| **Search prospects** | "Find 10 VP of Sales at B2B SaaS, 200–500 employees, US" | Dropleads primary → Deepline Native Prospector fallback; returns name, title, company, LinkedIn, email |
| **Research accounts** | "Research stripe.com" | Apollo → Crustdata → Exa web; returns description, headcount, funding, tech stack, HQ |
| **Verify emails** | "Is jsmith@acme.com safe to send?" | LeadMagic → ZeroBounce; returns valid/invalid + MX provider + sub-status |
| **Find LinkedIn URLs** | "LinkedIn for Tom Nguyen at Notion" | Apollo people match → Apollo search; returns URL + confidence level |
| **Build company lists** | "Find 25 fintech companies in NYC, 100–500 employees" | Apollo company search; returns name, domain, headcount, industry, description |

Every response includes a mandatory **Sources & Confidence** section: which providers ran, what came back verified vs. missing, and a recommended next step. The agent is explicit about data gaps — it won't invent emails or paper over obfuscated last names.

---

## How it works

```
Your query
    │
    ▼
Deep Agents (LangGraph)          ← orchestration, tool-calling, conversation memory
    │  model: claude-opus-4-6 / gpt-4o / gemini-2.0-flash
    │  tools: search_prospects, enrich_person, verify_email, ...
    │
    │  System prompt includes live Deepline skill docs fetched at startup —
    │  the agent knows each provider's filter syntax, known pitfalls, and
    │  exact waterfall order without you hardcoding any of that.
    │
    ▼
Deepline API (code.deepline.com) ← single key, 30+ providers underneath
    │
    ├── Dropleads       (person search — free, broad coverage)
    ├── Apollo          (person + company enrichment and search)
    ├── Hunter          (domain-level email pattern discovery)
    ├── LeadMagic       (email verification)
    ├── ZeroBounce      (email verification fallback)
    ├── Crustdata       (LinkedIn-native enrichment, headcount signals)
    ├── Exa             (live web research — news, bios, job postings)
    └── ... 25+ more
```

You don't manage individual provider keys or handle fallback logic — Deepline does that. One API key, one bill, one place to add providers.

### The LangGraph loop

The agent is a compiled LangGraph `StateGraph` returned by `create_gtm_agent()`. Each invocation runs:

1. Model receives user message + full conversation history + system prompt (with injected skill docs)
2. Model decides which tool(s) to call and with what parameters
3. Tools execute — each tool runs its own provider waterfall internally
4. Model receives tool results and either calls more tools or writes the final response
5. Final response always includes the structured Sources & Confidence section

This is a standard [ReAct](https://arxiv.org/abs/2210.03629) agent loop. The Deep Agents framework adds a planning tool, filesystem offloading for large context, and subagent spawning — though this reference implementation uses the basic loop. See the [deepagents docs](https://github.com/langchain-ai/deepagents) if you want to extend it.

<details>
<summary><strong>All 30+ providers</strong></summary>

**Data & Enrichment**

| Provider | What it does |
|---|---|
| [Crustdata](https://crustdata.com) | LinkedIn-native person & company enrichment, headcount signals |
| [People Data Labs](https://www.peopledatalabs.com) | Deep person & company enrichment, bulk operations |
| [Forager](https://forager.ai) | Person, company, and job data |
| [Prospeo](https://prospeo.io) | Person & company enrichment, email finding |
| [Apollo](https://apollo.io) | Person & company enrichment, search (BYOK) |
| [Dropleads](https://dropleads.io) | Person enrichment, email finding & verification |

**Email Finding & Verification**

| Provider | What it does |
|---|---|
| [Hunter](https://hunter.io) | Domain search, email finding, email verification |
| [Icypeas](https://icypeas.com) | Email search, verification, profile & company scraping |
| [Leadmagic](https://leadmagic.io) | Email & mobile finding, validation, job change detection |
| [ZeroBounce](https://zerobounce.net) | Email finding, batch validation, domain search |
| [AI Ark](https://aiark.ai) | Email finding, person & company search, personality analysis |

**Web & Research**

| Provider | What it does |
|---|---|
| [Exa](https://exa.ai) | AI-powered web search, company & people search, content extraction |
| [Firecrawl](https://firecrawl.dev) | Web scraping, crawling, structured extraction |
| [Parallel](https://parallel.ai) | AI-powered web research tasks |
| [Google Search](https://developers.google.com/custom-search) | Custom web search |

**Ad Intelligence**

| Provider | What it does |
|---|---|
| [Adyntel](https://adyntel.com) | Facebook, Google, TikTok ad monitoring & keyword tracking |

**Sequencers & Outreach**

| Provider | What it does |
|---|---|
| [Instantly](https://instantly.ai) | Email campaign management, lead import, performance stats |
| [Lemlist](https://lemlist.com) | Multi-channel email + LinkedIn sequencing |
| [SmartLead](https://smartlead.ai) | Email campaign management |
| [HeyReach](https://heyreach.io) | LinkedIn outreach campaign management |

**CRM & Data Warehouse**

| Provider | What it does |
|---|---|
| [HubSpot](https://hubspot.com) | CRM — read/write contacts, companies, deals |
| [Attio](https://attio.com) | CRM — contact and company records |
| [Salesforce](https://salesforce.com) | CRM — full object model access |
| [Snowflake](https://snowflake.com) | Direct SQL queries against your data warehouse |
| [BuiltWith](https://builtwith.com) | Tech stack detection |

</details>

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

Seven tools are registered on the agent. Each is a plain Python function — Deep Agents auto-generates the tool schema from the type annotations and docstring.

### `enrich_person`

**When to use:** You have a contact and need their work email, phone, or LinkedIn URL.

**Inputs:** At least one of `linkedin_url`, `email`, or `first_name + last_name`. Optionally `company_domain` or `company_name`.

**Waterfall:** Apollo people_match → Hunter combined_find (if domain + name) → Crustdata enrichment (if LinkedIn URL)

**Returns:** `{email, phone, title, company, linkedin_url, location, provider}`

**Cost:** ~0.17 credits/match

**Limitations:** Apollo free tier obfuscates last names on search results — use `enrich_person` with the exact name + domain to get around this.

---

### `search_prospects`

**When to use:** You need a list of people matching ICP criteria (title, seniority, location, company size, industry).

**Inputs:** Any combination of `job_title`, `job_level`, `company_name`, `company_domain`, `person_location`, `company_size_min`, `company_size_max`, `company_industry`, `limit` (default 10, max 25).

`job_level` accepted values: `owner`, `founder`, `c_suite`, `vp`, `director`, `manager`, `individual_contributor`

**Waterfall:** Dropleads (free, broad filters, no per-result cost) → Deepline Native Prospector (domain-specific, returns verified emails, 1.4 credits/result)

**Returns:** `{prospects: [{name, title, company, linkedin_url, email, location, company_size, industry, has_email}], count, total, provider}`

**Cost:** Dropleads is free. Deepline Native Prospector (fallback) is 1.4 credits/result.

**Limitations:** Dropleads doesn't always have emails — `has_email` tells you which results have one. Run `enrich_person` on results missing emails if needed.

---

### `research_company`

**When to use:** You need firmographic data on a company — headcount, funding, tech stack, description, HQ.

**Inputs:** `domain` (e.g. `"stripe.com"`) or `company_name`.

**Waterfall:** Apollo organization_enrich → Crustdata company_enrichment → Exa web research (live, most current)

**Returns:** `{name, domain, description, industry, headcount, funding, location, linkedin_url, website, technologies, provider}`

**Cost:** ~0.17 credits/call

**Limitations:** Apollo and Crustdata data can be 6–18 months stale. The Exa fallback hits live web sources and is more current. If headcount signals matter, follow up with `web_research` for recent job postings.

---

### `web_research`

**When to use:** Anything requiring live web data — C-suite name lookups, recent news, funding rounds, job postings, product launches, anything not in structured databases.

**Inputs:** `query` — a plain-language research question or instruction.

**Provider:** Exa research (neural web search + content extraction)

**Returns:** `{summary, query, provider}` — structured narrative with citations

**Cost:** Included in Deepline plan

**When the agent uses it automatically:** The system prompt instructs the agent to call `web_research` before `enrich_person` for C-suite title lookups, since database providers often have stale title data.

---

### `verify_email`

**When to use:** Before including an email in an outbound sequence. Always run this — a bounced email harms sender reputation.

**Inputs:** `email` (single address)

**Waterfall:** LeadMagic email_validation → ZeroBounce batch_validate (if LeadMagic returns unknown)

**Returns:** `{email, valid, status, safe_to_send, mx_provider, sub_status, provider}`

`safe_to_send` is `False` for valid addresses that are disposable or role-based (e.g. `info@`, `support@`).

**Cost:** Free–low

---

### `find_linkedin`

**When to use:** You have a name + company and need the LinkedIn profile URL before enriching.

**Inputs:** `first_name`, `last_name`, required. `company_name` or `company_domain` optional but strongly recommended to avoid false matches.

**Waterfall:** Apollo people_match (high confidence) → Apollo search_people (medium confidence)

**Returns:** `{linkedin_url, confidence, provider}` — `confidence` is `"high"`, `"medium"`, or `"none"`

**Cost:** Free

**Limitations:** Without a company, the medium-confidence Apollo search path can return wrong people. Always pass `company_name` or `company_domain` when you have it.

---

### `search_companies`

**When to use:** Building a target account list before finding contacts. Also useful for TAM analysis.

**Inputs:** Any combination of `industry`, `location`, `headcount_min`, `headcount_max`, `keywords`, `limit` (default 25, max 25).

**Provider:** Apollo company search (no fallback)

**Returns:** `{companies: [{name, domain, headcount, industry, description, location}], count, provider}`

**Cost:** ~0.17 credits/call

**Limitations:** Apollo keyword filtering is broad-match — results may include tangentially related companies. Use `research_company` or `web_research` to validate individual results.

---

### Cost summary

| Tool | Primary provider | Fallback | Cost |
|---|---|---|---|
| `enrich_person` | Hunter | Crustdata → Deepline Native | free–low |
| `search_prospects` | Dropleads (free) | Deepline Native Prospector | free / 1.4 credits |
| `research_company` | Crustdata | Exa | included |
| `web_research` | Exa | — | included |
| `verify_email` | LeadMagic | ZeroBounce | free–low |
| `find_linkedin` | Deepline Native Prospector | Exa | free–low |
| `search_companies` | Exa | — | included |

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
- **Slack OAuth token** — the `/slack/oauth_redirect` endpoint displays the bot token in the browser so you can copy it into Railway. Treat this page like a password: access it once, copy the token, then don't revisit. This is a demo tradeoff — a production multi-tenant app should store the token server-side and never display it.
- **HTTPS** — required in production. Use Railway's automatic TLS or a reverse proxy (nginx, Caddy). The API key is sent as a bearer token and must not travel over plain HTTP.

**Known limitations of this reference implementation** (out of scope for a demo, relevant if you productionize it):

- **Slack conversation history is in-memory** — thread context is lost on restart. A production bot should persist thread history to Redis or a database.
- **No rate limiting** — the `/chat` endpoints have no per-user or per-IP throttling. Add this at the reverse proxy layer (nginx, Caddy) or via FastAPI middleware if you expose the server publicly.
- **Single Slack workspace** — the OAuth flow exchanges a code for a bot token and asks you to set it manually. A multi-workspace distribution would store tokens per team in a database.

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
