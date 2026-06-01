"""Create or update the optional Anthropic Managed Agent shell.

The normal REST, web, and Slack surfaces stream through Deepline's native v2
`deeplineagent` endpoint. This setup script only provisions an Anthropic
Managed Agent for operators who still want an Anthropic-hosted session shell.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

CONFIG_PATH = Path(__file__).parent / ".agent_config.json"

SYSTEM_PROMPT = """\
You are a concise Deepline GTM operator.

Deepline tools, provider credentials, billing, plays, and native chat are
configured through Deepline v2 by the broker. Do not set up local credentials,
do not ask users for provider API keys, and do not perform infrastructure
bootstrap steps. Return final GTM results only.

For multi-record work, pilot a small sample, report expected cost and output
shape, and wait for approval before scaling the run.
"""


def main() -> None:
    client = anthropic.Anthropic()
    existing = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}

    if env_id := existing.get("environment_id"):
        print(f"Reusing environment: {env_id}")
    else:
        env = client.beta.environments.create(
            name=f"deepline-managed-v2-{os.getpid()}",
            config={"type": "cloud", "networking": {"type": "unrestricted"}},
        )
        env_id = env.id
        print(f"Created environment: {env_id}")

    tools = [{"type": "agent_toolset_20260401", "default_config": {"enabled": True}}]

    if agent_id := existing.get("agent_id"):
        print(f"Updating agent: {agent_id}")
        agent = client.beta.agents.update(
            agent_id=agent_id,
            version=existing.get("agent_version", 1),
            name="Deepline GTM Agent",
            model="claude-opus-4-6",
            system=SYSTEM_PROMPT,
            tools=tools,
        )
    else:
        agent = client.beta.agents.create(
            name="Deepline GTM Agent",
            model="claude-opus-4-6",
            description="Deepline GTM operator shell for native v2 workflows.",
            system=SYSTEM_PROMPT,
            tools=tools,
        )
        print(f"Created agent: {agent.id}")

    config = {
        "agent_id": agent.id,
        "agent_version": agent.version,
        "environment_id": env_id,
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"Saved to {CONFIG_PATH}")
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
