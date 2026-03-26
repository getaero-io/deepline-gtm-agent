# deepline-gtm-agent

GTM automation agent powered by [Deepline](https://deepline.com) + [Deep Agents](https://github.com/langchain-ai/deepagents).

30+ enrichment and outreach providers. One agent. Zero boilerplate.

## What it does

- **Enrich contacts** — work email, phone, job title from LinkedIn URL or name + company
- **Search prospects** — people matching ICP criteria (title, level, company size, geo)
- **Research accounts** — firmographics, tech stack, funding, headcount signals
- **Verify emails** — deliverability check before any send
- **Build company lists** — TAM discovery by industry, location, headcount
- **Find LinkedIn URLs** — name + company → profile URL

All backed by Deepline's 30+ provider waterfall: Apollo, ContactOut, Wiza, RocketReach, Crustdata, PeopleDataLabs, LeadMagic, ZeroBounce, and more.

## Install

```bash
pip install deepline-gtm-agent
```

You'll also need:
- [Deepline CLI](https://code.deepline.com) installed and authenticated (`deepline auth status`)
- `ANTHROPIC_API_KEY` set (or swap for OpenAI/Google — see below)

## Quickstart

```python
from deepline_gtm_agent import create_gtm_agent

agent = create_gtm_agent()

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Find the work email for Reid Hoffman at Greylock and verify it."
    }]
})

print(result["messages"][-1].content)
```

## Examples

**Enrich a contact from LinkedIn:**
```python
agent.invoke({"messages": [{"role": "user", "content":
    "Enrich https://www.linkedin.com/in/reidhoffman/ — I need email + phone."
}]})
```

**Find VP of Sales prospects:**
```python
agent.invoke({"messages": [{"role": "user", "content":
    "Find 10 VP of Sales at B2B SaaS companies, 200-500 employees, US-based."
}]})
```

**Research a target account:**
```python
agent.invoke({"messages": [{"role": "user", "content":
    "Research rippling.com — headcount, funding, tech stack, ICP fit."
}]})
```

## Add your own tools

The agent accepts any Deep Agents-compatible tool function:

```python
def check_crm(email: str) -> dict:
    """Check if a contact already exists in HubSpot CRM."""
    # your HubSpot logic here
    ...

agent = create_gtm_agent(extra_tools=[check_crm])
```

## Swap the model

Works with any LLM that supports tool calling:

```python
# OpenAI
agent = create_gtm_agent(model="openai:gpt-4o")

# Google
agent = create_gtm_agent(model="google:gemini-2.0-flash")
```

## Available tools

| Tool | What it calls |
|------|--------------|
| `enrich_person` | ContactOut → Wiza → Apollo waterfall |
| `search_prospects` | Wiza (free) → Apollo fallback |
| `research_company` | Apollo → Crustdata |
| `verify_email` | LeadMagic → ZeroBounce |
| `find_linkedin` | RocketReach → Apollo |
| `search_companies` | Apollo organization search |

## Architecture

```
User prompt
    │
    ▼
create_gtm_agent()          ← Deep Agents framework
    │   model: Claude Opus 4.6
    │   system_prompt: GTM_SYSTEM_PROMPT
    │   tools: [enrich_person, search_prospects, ...]
    │
    ▼
Tool calls → deepline_execute(operation, payload)
                │
                ▼
            deepline CLI
                │
                ▼
        30+ providers via Deepline API
        (ContactOut, Wiza, Apollo, RocketReach,
         Crustdata, LeadMagic, ZeroBounce, ...)
```

Each tool is a plain Python function — no framework magic, no DSL. Deep Agents reads the docstring + type hints and generates the tool schema automatically.

## Why Deepline

- **One API key, 30+ providers** — no managing individual credentials
- **Built-in waterfall** — automatic fallback across providers per field
- **Credit-based pricing** — pay per result, not per API call
- **CLI-first** — works in any Python environment, no server required

## License

MIT
