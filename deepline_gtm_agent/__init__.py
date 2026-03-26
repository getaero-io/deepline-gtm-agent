"""
deepline-gtm-agent: GTM automation agent powered by Deepline + Deep Agents.

Drop-in GTM agent that combines 30+ enrichment and outreach providers via
Deepline with the Deep Agents orchestration framework.

Usage:
    from deepline_gtm_agent import create_gtm_agent

    agent = create_gtm_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
"""

from deepline_gtm_agent.agent import create_gtm_agent
from deepline_gtm_agent.tools import (
    enrich_person,
    search_prospects,
    research_company,
    verify_email,
    find_linkedin,
    search_companies,
)

__all__ = [
    "create_gtm_agent",
    "enrich_person",
    "search_prospects",
    "research_company",
    "verify_email",
    "find_linkedin",
    "search_companies",
]
