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
    # Recipes
    ("recipes/build-tam.md", "TAM build recipe — account + contact sourcing from scratch"),
    ("recipes/linkedin-url-lookup.md", "LinkedIn URL lookup recipe — resolve profiles from name/company"),
    ("recipes/portfolio-prospecting.md", "Portfolio prospecting recipe — VC/PE portfolio company outreach"),
    ("actor-contracts.md", "Apify actor contracts — validated actor IDs and payload schemas"),
]


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

    if sections:
        return "\n\n---\n\n".join(sections)
    return ""


# Sync wrapper for use at startup (before event loop)
def load_skill_docs_sync() -> str:
    try:
        return asyncio.run(load_skill_docs())
    except RuntimeError:
        # Already inside an event loop (e.g. during testing)
        return ""
