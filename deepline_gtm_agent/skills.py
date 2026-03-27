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
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)

SKILLS_BASE = "https://code.deepline.com/.well-known/skills/gtm-meta-skill"

# The docs that matter most for the agent's decision-making.
# Ordered by importance — SKILL.md is routing, the phase docs are execution.
CORE_SKILL_DOCS = [
    ("SKILL.md", "GTM Skill — routing, defaults, approval gates, provider overview"),
    ("finding-companies-and-contacts.md", "Finding companies and contacts — search patterns, filter schemas, parallel execution"),
    ("enriching-and-researching.md", "Enriching and researching — waterfall patterns, email/LinkedIn lookup, coalescing"),
    ("provider-playbooks/apollo.md", "Apollo playbook — filter syntax, seniority values, cost notes"),
    ("provider-playbooks/hunter.md", "Hunter playbook — domain email finder, verification"),
    ("provider-playbooks/zerobounce.md", "ZeroBounce playbook — email validation, sub_status codes"),
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
    Fetch core skill docs concurrently and return them as a single markdown string
    to inject into the system prompt.
    """
    tasks = [_fetch(f"{SKILLS_BASE}/{path}") for path, _ in CORE_SKILL_DOCS]
    results = await asyncio.gather(*tasks)

    sections = []
    for (path, description), content in zip(CORE_SKILL_DOCS, results):
        if content:
            sections.append(f"## Skill doc: {description}\n\n{content}")
        else:
            logger.warning("Skill doc unavailable: %s", path)

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
