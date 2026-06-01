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
    config = _load_config()
    safe_title = title.replace("`", "").replace("\n", " ")[:80] or "Deepline GTM"
    session = client.beta.sessions.create(
        agent=config["agent_id"],
        environment_id=config["environment_id"],
        title=safe_title,
        resources=extra_resources or [],
    )
    return session.id


def send_message(client: anthropic.Anthropic, session_id: str, text: str) -> None:
    client.beta.sessions.events.send(
        session_id=session_id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
    )


def _parse_event(event) -> dict | None:
    etype = getattr(event, "type", None)
    if etype == "agent.message":
        for block in getattr(event, "content", []):
            if getattr(block, "type", None) == "text":
                return {"type": "text", "text": block.text}
    if etype == "agent.tool_use":
        return {"type": "tool", "name": getattr(event, "name", "?")}
    if etype == "session.status_idle":
        stop_reason = getattr(event, "stop_reason", None)
        stop_type = getattr(stop_reason, "type", None) if stop_reason else None
        if stop_type == "requires_action":
            return None
        return {"type": "done", "reason": stop_type or "idle"}
    if etype == "session.status_terminated":
        return {"type": "done", "reason": "terminated"}
    return None


def stream_events(client: anthropic.Anthropic, session_id: str) -> Iterator[dict]:
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        for event in stream:
            parsed = _parse_event(event)
            if parsed:
                yield parsed
                if parsed["type"] == "done":
                    return


def run_prompt(
    client: anthropic.Anthropic,
    prompt: str,
    bootstrap: bool = False,
    title: str | None = None,
) -> Iterator[dict]:
    session_id = create_session(client, title=title or prompt[:60])
    send_message(client, session_id, f"{TASK_PREFIX}{prompt}")
    yield from stream_events(client, session_id)
