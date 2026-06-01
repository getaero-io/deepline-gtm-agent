"""Compatibility entrypoint for legacy root tools.

New managed-agent code should use :class:`deepline_gtm_agent.v2_client.DeeplineV2Client`
directly. This module remains only so old LangGraph tool functions keep routing
through Deepline's v2 SDK-facing API contract during the deprecation window.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from deepline_gtm_agent.v2_client import DEFAULT_DEEPLINE_BASE_URL, DeeplineV2Client

DEEPLINE_API_BASE = (
    os.environ.get("DEEPLINE_HOST_URL")
    or os.environ.get("DEEPLINE_API_BASE_URL")
    or DEFAULT_DEEPLINE_BASE_URL
)


def deepline_execute(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a Deepline v2 tool synchronously for legacy callers."""

    async def _run() -> dict[str, Any]:
        return await DeeplineV2Client(base_url=DEEPLINE_API_BASE).execute_tool(
            operation,
            payload,
            include_tool_metadata=True,
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())
    raise RuntimeError(
        "deepline_execute is synchronous and cannot be called from a running event loop; "
        "use DeeplineV2Client.execute_tool instead."
    )
