"""
GTM agent factory using the Deep Agents framework.
"""

from typing import Optional, Sequence, Any, Callable
from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from deepline_gtm_agent.prompts import GTM_SYSTEM_PROMPT
from deepline_gtm_agent.skills import load_skill_docs
from deepline_gtm_agent.tools import (
    enrich_person,
    search_prospects,
    research_company,
    verify_email,
    find_linkedin,
    search_companies,
)

# All Deepline GTM tools available to the agent
DEEPLINE_GTM_TOOLS: list[Callable] = [
    enrich_person,
    search_prospects,
    research_company,
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
    **kwargs: Any,
):
    """
    Create a GTM agent powered by Deepline + Deep Agents.

    The agent has access to 30+ enrichment and outreach providers via Deepline
    and is prompted to act as a GTM automation specialist.

    Args:
        model: LLM to use. Defaults to Claude Opus 4.6 via LangChain's init_chat_model.
               Also accepts "openai:gpt-4o", "google:gemini-2.0-flash", etc.
        system_prompt: Override the default GTM system prompt.
        extra_tools: Additional tool functions to register alongside Deepline tools.
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
    all_tools: list = list(DEEPLINE_GTM_TOOLS)
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
