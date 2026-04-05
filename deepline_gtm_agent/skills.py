"""
Fetches Deepline skill docs from the public CDN and injects them into the agent's
system prompt so the deployed agent has the same guidance as local CLI + skills.

Skill docs live at: https://code.deepline.com/.well-known/skills/gtm-meta-skill/
They encode validated provider schemas, waterfall patterns, filter syntax, and
known pitfalls — the same knowledge installed via `npx skills add` locally.

Loaded once at startup and cached. Falls back gracefully if the CDN is unreachable.
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

SKILLS_BASE = "https://code.deepline.com/.well-known/skills/gtm-meta-skill"

# All skill docs to load — ordered by importance.
# Phase docs first (routing/execution), then all provider playbooks.
CORE_SKILL_DOCS = [
    # Routing + phase docs
    ("SKILL.md", "GTM Skill — routing, defaults, approval gates, provider overview"),
    ("finding-companies-and-contacts.md", "Finding companies and contacts — search patterns, filter schemas, parallel execution"),
    ("enriching-and-researching.md", "Enriching and researching — waterfall patterns, email/LinkedIn lookup, coalescing"),
    ("writing-outreach.md", "Writing outreach — email templates, personalization, scoring, qualification"),
    # Provider playbooks — one per integration
    ("provider-playbooks/hubspot.md", "HubSpot playbook — CRM: contacts, companies, deals, notes, tasks"),
    ("provider-playbooks/salesforce.md", "Salesforce playbook — CRM: leads, contacts, accounts, opportunities"),
    ("provider-playbooks/attio.md", "Attio playbook — CRM: person, company, deal records"),
    ("provider-playbooks/apollo.md", "Apollo playbook — filter syntax, seniority values, cost notes"),
    ("provider-playbooks/crustdata.md", "Crustdata playbook — company enrichment, people search, LinkedIn data"),
    ("provider-playbooks/hunter.md", "Hunter playbook — domain email finder, combined find, verification"),
    ("provider-playbooks/dropleads.md", "Dropleads playbook — free people search, bulk enrichment"),
    ("provider-playbooks/instantly.md", "Instantly playbook — campaign management, lead sequencing"),
    ("provider-playbooks/lemlist.md", "Lemlist playbook — campaign sequences, LinkedIn + email outreach"),
    ("provider-playbooks/smartlead.md", "Smartlead playbook — campaigns, email accounts, lead management"),
    ("provider-playbooks/heyreach.md", "HeyReach playbook — LinkedIn automation, campaign management"),
    ("provider-playbooks/zerobounce.md", "ZeroBounce playbook — email validation, sub_status codes"),
    ("provider-playbooks/exa.md", "Exa playbook — AI web research, company/people search, news"),
    ("provider-playbooks/firecrawl.md", "Firecrawl playbook — web scraping, site crawl, extract"),
    ("provider-playbooks/apify.md", "Apify playbook — actor selection, LinkedIn scraping, data extraction"),
    ("provider-playbooks/leadmagic.md", "LeadMagic playbook — email finder, mobile finder, job change detection"),
    ("provider-playbooks/peopledatalabs.md", "PeopleDataLabs playbook — bulk enrichment, people/company search"),
    ("provider-playbooks/icypeas.md", "Icypeas playbook — email search, bulk search, company lookup"),
    ("provider-playbooks/prospeo.md", "Prospeo playbook — person/company enrichment and search"),
    ("provider-playbooks/forager.md", "Forager playbook — person role search, organization search, job listings"),
    ("provider-playbooks/deepline_native.md", "Deepline Native playbook — prospector, waterfall enrichment, phone finder"),
    ("provider-playbooks/adyntel.md", "Adyntel playbook — ad intelligence: Google, Facebook, LinkedIn, TikTok"),
    ("provider-playbooks/builtwith.md", "BuiltWith playbook — tech stack lookup, domain technology profiling"),
    ("provider-playbooks/serper.md", "Serper playbook — Google search, Google Maps search"),
    ("provider-playbooks/parallel.md", "Parallel playbook — parallel execution, findall, task orchestration"),
    ("provider-playbooks/deeplineagent.md", "DeeplineAgent playbook — AI inference, custom logic steps"),
    ("provider-playbooks/ai_ark.md", "AI Ark playbook — email finder, people search, mobile phone"),
    ("provider-playbooks/cloudflare.md", "Cloudflare playbook — domain crawl and intelligence"),
    # Local skills (not from CDN)
    # /last30days is handled inline — see LOCAL_SKILL_DOCS below
    # Recipes
    ("recipes/build-tam.md", "TAM build recipe — account + contact sourcing from scratch"),
    ("recipes/linkedin-url-lookup.md", "LinkedIn URL lookup recipe — resolve profiles from name/company"),
    ("recipes/portfolio-prospecting.md", "Portfolio prospecting recipe — VC/PE portfolio company outreach"),
    ("actor-contracts.md", "Apify actor contracts — validated actor IDs and payload schemas"),
]


LOCAL_SKILL_DOCS = """## Skill doc: /last30days — recently hired contacts search

**Trigger**: User types `/last30days [criteria]` or asks for "recent hires" / "hired in last 30 days".

**What to do**:
1. Call `search_prospects` with `recently_hired_months=1` plus any filters the user provided.
   - This routes to Icypeas, which has native hire-date filtering.
   - Dropleads does NOT support this filter — always use Icypeas via `recently_hired_months`.
2. For city-level location (e.g. NYC, San Francisco), also pass `person_location` — Icypeas handles both together.
3. Return the full result table with name, title, company, LinkedIn URL.
4. Suggest next step: enrich emails for the contacts found.

**Example call**:
```
search_prospects(
    job_title="VP of Sales",
    job_level="VP",
    geo="United States",
    industry="SaaS",
    recently_hired_months=1
)
```

**Why this matters**: Recently hired VPs, Directors, and C-Suite are in "new job" mode — high intent to buy new tools, build new teams, and change vendors. This is one of the highest-signal prospecting triggers in GTM.
"""


ORGCHART_SKILL_DOC = """## Skill doc: /orgchart - org chart and account mapping

**Trigger**: User asks to build an org chart, map an account, identify decision makers, find someone's manager/peers/reports, or map organizational hierarchy around a person.

**What to do**:
1. Call `build_org_chart` with the target's linkedin_url or first_name + last_name + company_domain.
2. The tool discovers ALL employees via Apollo (4 seniority tiers) + Dropleads, fetches job listings from Crustdata for team structure, and infers hierarchy using multi-feature scoring: seniority gap + team match + geo proximity + experience delta.
3. Return the structured result including the summary (manager, peers, reports).
4. Sumble is NOT used as a primary source - only as a fallback validation check.

**Example calls**:
```
build_org_chart(linkedin_url="https://linkedin.com/in/manpreet-singh", company_domain="stripe.com", company_name="Stripe")
build_org_chart(first_name="Jane", last_name="Doe", company_domain="acme.com", company_name="Acme Corp")
```

**Manager prediction model**: seniority gap (+10 for 1 level above) + team match (+8 same team) + geo (+2 same city) + experience delta (+2 for 3+ yrs, +3 for 8+ yrs). Min threshold 5.

**Returns**: `{people, hierarchy, summary}` where summary has manager, peers, direct_reports, total_people.
"""


WATERFALL_SKILL_DOC = """## Skill doc: Waterfall.io integration

**When to use Waterfall vs Deepline providers:**
- Waterfall aggregates 30+ data vendors behind one API - higher coverage than any single Deepline provider
- Use `waterfall_prospect` when you need to find contacts at a company and want maximum coverage
- Use `waterfall_enrich_contact` after the Deepline waterfall if Deepline providers missed
- Use `waterfall_job_change` for detecting job changes (unique capability - not in Deepline)
- Use `waterfall_verify_email` as a backup to LeadMagic/ZeroBounce for email verification
- Waterfall is async (POST to launch, polls until done) - expect 5-15s per request
- Requires WATERFALL_API_KEY env var

**Tool selection guide:**
| Need | Deepline first | Waterfall fallback |
|------|---------------|-------------------|
| Find contacts at company | company_to_contact_by_role_waterfall | waterfall_prospect |
| Enrich person | name_and_company_to_email_waterfall | waterfall_enrich_contact |
| Phone numbers | contact_to_phone_waterfall | waterfall_enrich_phone |
| Company data | crustdata_company_enrichment | waterfall_enrich_company |
| Search contacts | dropleads/apollo/icypeas | waterfall_search_contacts |
| Job change detection | N/A | waterfall_job_change (unique) |
| Email verification | leadmagic + zerobounce | waterfall_verify_email |
"""


async def _fetch(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning("Failed to fetch skill doc %s: %s", url, e)
    return ""


async def load_skill_docs() -> str:
    """
    Fetch all skill docs concurrently and return them as a single markdown string
    to inject into the system prompt.
    """
    tasks = [_fetch(f"{SKILLS_BASE}/{path}") for path, _ in CORE_SKILL_DOCS]
    results = await asyncio.gather(*tasks)

    sections = []
    loaded = 0
    for (path, description), content in zip(CORE_SKILL_DOCS, results):
        if content:
            sections.append(f"## Skill doc: {description}\n\n{content}")
            loaded += 1
        else:
            logger.warning("Skill doc unavailable: %s", path)

    logger.info("Loaded %d/%d skill docs", loaded, len(CORE_SKILL_DOCS))

    # Append local skill docs (not from CDN)
    sections.append(f"## Skill doc: /last30days workflow\n\n{LOCAL_SKILL_DOCS}")
    sections.append(ORGCHART_SKILL_DOC)
    sections.append(WATERFALL_SKILL_DOC)

    if sections:
        return "\n\n---\n\n".join(sections)
    return LOCAL_SKILL_DOCS


# Sync wrapper for use at startup (before event loop)
def load_skill_docs_sync() -> str:
    try:
        return asyncio.run(load_skill_docs())
    except RuntimeError:
        # Already inside an event loop (e.g. during testing)
        return ""
