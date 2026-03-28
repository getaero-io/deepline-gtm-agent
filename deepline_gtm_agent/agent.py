"""
GTM agent factory using the Deep Agents framework.
"""

import logging
from typing import Optional, Sequence, Any, Callable

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from deepline_gtm_agent.prompts import GTM_SYSTEM_PROMPT
from deepline_gtm_agent.skills import load_skill_docs
from deepline_gtm_agent.dynamic_tools import load_tool_catalog, make_deepline_call_tool
from deepline_gtm_agent.tools import (
    enrich_person,
    waterfall_enrich,
    search_prospects,
    research_company,
    web_research,
    verify_email,
    find_linkedin,
    search_companies,
)

logger = logging.getLogger(__name__)

# High-level GTM tools with waterfall logic and smart defaults.
# These are the primary interface for common GTM operations.
GTM_HIGH_LEVEL_TOOLS: list[Callable] = [
    waterfall_enrich,
    enrich_person,
    search_prospects,
    research_company,
    web_research,
    verify_email,
    find_linkedin,
    search_companies,
]


async def build_system_prompt(base: Optional[str] = None) -> str:
    """Fetch live skill docs from Deepline CDN and append to the base prompt."""
    skill_docs = await load_skill_docs()
    base_prompt = base or GTM_SYSTEM_PROMPT
    if skill_docs:
        return f"{base_prompt}\n\n---\n\n# Deepline Skill Documentation\n\nThe following docs are fetched live from Deepline's skill CDN. They contain validated provider schemas, waterfall patterns, and known pitfalls.\n\n{skill_docs}"
    return base_prompt


def create_gtm_agent(
    model: str = "anthropic:claude-opus-4-6",
    system_prompt: Optional[str] = None,
    extra_tools: Optional[Sequence[BaseTool | Callable | dict[str, Any]]] = None,
    skill_docs: Optional[str] = None,
    tool_catalog: Optional[list[dict]] = None,
    **kwargs: Any,
):
    """
    Create a GTM agent powered by Deepline + Deep Agents.

    The agent has access to:
    - 8 high-level GTM tools (waterfall enrichment, prospect search, company research, etc.)
    - `deepline_call`: a passthrough to all 438+ Deepline integrations (HubSpot, Salesforce,
      Attio, Instantly, Lemlist, Smartlead, HeyReach, Apollo, Crustdata, Firecrawl, Apify, …)

    The tool catalog is fetched dynamically at startup and cached for 24h, so new Deepline
    integrations are automatically available without code changes.

    Args:
        model: LLM to use. Defaults to Claude Opus 4.6 via LangChain's init_chat_model.
               Also accepts "openai:gpt-4o", "google:gemini-2.0-flash", etc.
        system_prompt: Override the default GTM system prompt.
        extra_tools: Additional tool functions to register alongside Deepline tools.
        skill_docs: Pre-fetched Deepline skill docs string (injected at startup by server.py).
        tool_catalog: Pre-fetched Deepline tool catalog list (injected at startup by server.py).
        **kwargs: Forwarded to `create_deep_agent` (e.g. checkpointer, store, debug).

    Returns:
        A compiled LangGraph StateGraph ready to invoke.

    Example::

        agent = create_gtm_agent()
        result = agent.invoke({
            "messages": [{
                "role": "user",
                "content": "Find the work email for Reid Hoffman at Greylock"
            }]
        })
        print(result["messages"][-1].content)
    """
    # Load catalog (use pre-loaded if provided, else fetch now)
    catalog = tool_catalog
    if catalog is None:
        logger.info("Loading Deepline tool catalog...")
        catalog = load_tool_catalog()

    # Build the deepline_call passthrough with full catalog embedded in description
    deepline_call_tool = make_deepline_call_tool(catalog)
    logger.info("deepline_call tool registered (%d tools in catalog)", len(catalog))

    # Assemble all tools
    all_tools: list = list(GTM_HIGH_LEVEL_TOOLS) + [deepline_call_tool]
    if extra_tools:
        all_tools.extend(extra_tools)

    # Build final system prompt: base + injected skill docs (if pre-fetched)
    final_prompt = system_prompt or GTM_SYSTEM_PROMPT
    if skill_docs:
        final_prompt = (
            f"{final_prompt}\n\n---\n\n"
            "# Deepline Skill Documentation\n\n"
            "The following docs are fetched live from Deepline's skill CDN. "
            "They contain validated provider schemas, waterfall patterns, and known pitfalls. "
            "Treat them as authoritative.\n\n"
            f"{skill_docs}"
        )

    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=final_prompt,
        **kwargs,
    )
