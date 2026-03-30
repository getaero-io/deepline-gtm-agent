# deepline-gtm-agent

Open-source GTM agent built on [Deepline](https://deepline.com) + [Deep Agents](https://github.com/langchain-ai/deepagents) (LangGraph).

This is a reference implementation — a working starter kit you can deploy as-is or fork and extend. Deepline handles the data layer (441+ integrations across enrichment, CRM, and outreach). Deep Agents handles the orchestration (LangGraph-powered agent loop). You write the business logic.

Inspired by ["How we built LangChain's GTM Agent"](https://blog.langchain.com/how-we-built-langchains-gtm-agent/) — this repo is the Deepline-powered version of that architecture, deployable in minutes.

**API portal:** [code.deepline.com](https://code.deepline.com) — get your `DEEPLINE_API_KEY` here
**GitHub:** [github.com/jptoor/deepline-gtm-agent](https://github.com/jptoor/deepline-gtm-agent)

---

## What it does

The agent handles core GTM workflows, each backed by a waterfall of data providers:

| Workflow | What you ask | What happens |
|---|---|---|
| **Enrich contacts** | "Find the email for Jane Smith at Acme" | 10-provider waterfall: Dropleads → Hunter → LeadMagic → Deepline Native → Crustdata → Icypeas → Prospeo → AI Ark → PDL → Forager |
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

```
Your query
    │
    ▼
Deep Agents (LangGraph)          ← orchestration, tool-calling, conversation memory
    │  model: claude-opus-4-6 / gpt-4o / gemini-2.0-flash
    │
    │  8 high-level tools: waterfall_enrich, enrich_person, search_prospects,
    │    research_company, web_research, verify_email, find_linkedin, search_companies
    │
    │  + deepline_call: passthrough to all 441+ Deepline integrations
    │    (HubSpot, Salesforce, Attio, Lemlist, Instantly, Smartlead, HeyReach,
    │     Apollo, Crustdata, Firecrawl, Apify, Exa, BuiltWith, Adyntel, …)
    │
    ▼
Deepline API (code.deepline.com) ← single key, 441+ integrations underneath
    │
    ├── Dropleads       (person search — free, broad coverage)
    ├── Hunter          (domain-level email pattern discovery)
    ├── LeadMagic       (email + mobile finding, validation)
    ├── Crustdata       (LinkedIn-native enrichment, headcount signals)
    ├── Icypeas         (email search, recently-hired filtering)
    ├── Prospeo         (person enrichment, 30+ search filters)
    ├── AI Ark          (email finding, person & company search)
    ├── People Data Labs (deep person & company enrichment)
    ├── Forager         (person & company data, phone recovery)
    ├── Exa             (live web research — news, bios, job postings)
    └── ... 430+ more (CRM, outreach, scraping, ad intelligence)
```

You don't manage individual provider keys or handle fallback logic — Deepline does that. One API key, one bill, one place to add providers.

### The LangGraph loop

The agent is a compiled LangGraph `StateGraph` returned by `create_gtm_agent()`. Each invocation runs:

1. Model receives user message + full conversation history + system prompt
2. Model decides which tool(s) to call and with what parameters
3. Tools execute — each high-level tool runs its own provider waterfall internally; `deepline_call` routes directly to any of the 441 integrations
4. Model receives tool results and either calls more tools or writes the final response

This is a standard [ReAct](https://arxiv.org/abs/2210.03629) agent loop. The Deep Agents framework handles the state machine, tool routing, and conversation persistence.

<details>
<summary><strong>All providers</strong></summary>

**Data & Enrichment**

| Provider | What it does |
|---|---|
| [Crustdata](https://crustdata.com) | LinkedIn-native person & company enrichment, headcount signals |
| [People Data Labs](https://www.peopledatalabs.com) | Deep person & company enrichment, bulk operations |
| [Forager](https://forager.ai) | Person, company, and job data; strong for phone recovery |
| [Prospeo](https://prospeo.io) | Person & company enrichment, email finding, 30+ search filters |
| [Apollo](https://apollo.io) | Person & company enrichment, search |
| [Dropleads](https://dropleads.io) | Person search, email finding — free tier, broad coverage |
| [Icypeas](https://icypeas.com) | Email search, recently-hired filtering, profile scraping |
| [AI Ark](https://aiark.ai) | Email finding, person & company search |

**Email Finding & Verification**

| Provider | What it does |
|---|---|
| [Hunter](https://hunter.io) | Domain search, email finding, email verification |
| [Leadmagic](https://leadmagic.io) | Email & mobile finding, validation, job change detection |
| [ZeroBounce](https://zerobounce.net) | Email finding, batch validation, domain search |

**Web & Research**

| Provider | What it does |
|---|---|
| [Exa](https://exa.ai) | AI-powered web search, company & people search, content extraction |
| [Firecrawl](https://firecrawl.dev) | Web scraping, crawling, structured extraction |
| [Apify](https://apify.com) | LinkedIn scraper, Google Maps, custom actors |
| [Google Search](https://developers.google.com/custom-search) | Custom web search |

**Ad Intelligence**

| Provider | What it does |
|---|---|
| [Adyntel](https://adyntel.com) | Facebook, Google, TikTok ad monitoring & keyword tracking |
| [BuiltWith](https://builtwith.com) | Tech stack detection |

**Sequencers & Outreach**

| Provider | What it does |
|---|---|
| [Instantly](https://instantly.ai) | Email campaign management, lead import, performance stats |
| [Lemlist](https://lemlist.com) | Multi-channel email + LinkedIn sequencing |
| [SmartLead](https://smartlead.ai) | Email campaign management |
| [HeyReach](https://heyreach.io) | LinkedIn outreach campaign management |

**CRM & Data**

| Provider | What it does |
|---|---|
| [HubSpot](https://hubspot.com) | CRM — read/write contacts, companies, deals, notes, tasks |
| [Attio](https://attio.com) | CRM — contacts, companies, list entries |
| [Salesforce](https://salesforce.com) | CRM — leads, contacts, accounts, opportunities |
| [Snowflake](https://snowflake.com) | Direct SQL queries against your data warehouse |

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

**Waterfall (10 providers, stops on first hit):** Dropleads → Hunter → LeadMagic → Deepline Native → Crustdata → Icypeas → Prospeo → AI Ark → PeopleDataLabs → Forager

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
