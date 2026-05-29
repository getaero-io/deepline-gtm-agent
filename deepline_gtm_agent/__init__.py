"""Deepline GTM managed-agent broker utilities.

The default v2 runtime is the managed broker plus Deepline's native agent/chat
API. Legacy LangGraph helpers are imported lazily so installing the broker no
longer pulls Deep Agents or LangChain onto the default path.
"""

from deepline_gtm_agent.v2_client import DeeplineV2Client

__all__ = ["DeeplineV2Client", "create_gtm_agent", "build_prospect_list_job"]


def create_gtm_agent(*args, **kwargs):
    """Create the LangGraph GTM agent lazily (self-hosted path)."""
    from deepline_gtm_agent.agent import create_gtm_agent as _create_gtm_agent

    return _create_gtm_agent(*args, **kwargs)


def build_prospect_list_job(*args, **kwargs):
    """Build a durable prospect list job lazily (uses LangGraph path)."""
    from deepline_gtm_agent.tools import build_prospect_list_job as _fn

    return _fn(*args, **kwargs)
