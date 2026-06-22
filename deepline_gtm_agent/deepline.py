"""Synchronous compatibility helper for Deepline tool execution.

New managed-agent code should use :class:`deepline_gtm_agent.v2_client.DeeplineV2Client`
directly. This module keeps the v2 SDK path as the default while preserving the
legacy local CLI fallback for LangGraph/local callers without a Deepline API key.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import Any

from deepline_gtm_agent.v2_client import DEFAULT_DEEPLINE_BASE_URL, DeeplineV2Client

DEEPLINE_API_BASE = (
    os.environ.get("DEEPLINE_HOST_URL")
    or os.environ.get("DEEPLINE_API_BASE_URL")
    or DEFAULT_DEEPLINE_BASE_URL
)


def deepline_execute(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a Deepline tool synchronously, preferring the v2 SDK."""

    if not os.environ.get("DEEPLINE_API_KEY"):
        return _deepline_execute_cli(operation, payload)

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


def _deepline_execute_cli(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute through the installed local Deepline CLI for legacy callers."""

    result = subprocess.run(
        ["deepline", "tools", "execute", operation, "--input", json.dumps(payload), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"deepline tools execute failed for {operation}: {detail}")
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"deepline tools execute returned non-JSON output for {operation}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"deepline tools execute returned {type(parsed).__name__}, expected object")
    return parsed
