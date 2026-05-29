"""Optional Anthropic Managed Agent session client.

The production web/Slack broker uses Deepline's native v2 chat stream directly.
This module is retained for manual Anthropic Managed Agent experiments without
uploading local Deepline binaries, local auth files, or bootstrap scripts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import anthropic

CONFIG_PATH = Path(__file__).parent / ".agent_config.json"

TASK_PREFIX = (
    "Deepline is configured through workspace-scoped v2 API credentials on the broker. "
    "Do not bootstrap a local CLI or ask users for provider API keys. "
    "Return concise GTM results only.\n\n"
)


def _load_config() -> dict:
    agent_id = os.environ.get("MANAGED_AGENT_ID")
    env_id = os.environ.get("MANAGED_ENVIRONMENT_ID")
    if agent_id and env_id:
        return {"agent_id": agent_id, "environment_id": env_id}
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"No {CONFIG_PATH} and MANAGED_AGENT_ID/MANAGED_ENVIRONMENT_ID not set. "
            "Run setup.py first or set env vars."
        )
    return json.loads(CONFIG_PATH.read_text())


def create_session(
    client: anthropic.Anthropic,
    title: str = "Deepline GTM",
    extra_resources: list[dict] | None = None,
) -> str:
    """Create a new Managed Agent session and return its session_id."""
    config = _load_config()
    resources = list(extra_resources or [])
    session = client.beta.sessions.create(
        agent_id=config["agent_id"],
        environment_id=config["environment_id"],
        display_name=title,
        resources=resources,
    )
    return session.id


def stream_events(
    client: anthropic.Anthropic,
    session_id: str,
    task: str,
) -> Iterator[anthropic.types.beta.sessions.SessionStreamEvent]:
    """Stream events from a session task."""
    with client.beta.sessions.stream(session_id=session_id, message=TASK_PREFIX + task) as stream:
        yield from stream
