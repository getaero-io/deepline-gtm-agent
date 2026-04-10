"""ONE-TIME SETUP — creates the Managed Agent + Environment on Anthropic.

Run once:
    python setup.py

Re-running updates the agent in place (new version). IDs persist in .agent_config.json.
"""

import json
import os
from pathlib import Path

import anthropic

CONFIG_PATH = Path(__file__).parent / ".agent_config.json"

SYSTEM_PROMPT = """\
You are a Deepline GTM operator running inside a sandboxed container with full
access to the Deepline platform via the `deepline` CLI at https://code.deepline.com.

## Bootstrap (run FIRST, before any real work)

```bash
mkdir -p ~/.local/bin ~/.local/deepline/code-deepline-com
cp /mnt/session/uploads/workspace/deepline ~/.local/bin/deepline
chmod +x ~/.local/bin/deepline
export PATH="$HOME/.local/bin:$PATH"
cp /mnt/session/uploads/workspace/deepline-auth.env ~/.local/deepline/code-deepline-com/.env
deepline auth status
```

## Deepline CLI reference

Run `deepline --help` for all commands. Key ones:
- `deepline tools list` / `deepline tools search <q>` - discover 441+ tools
- `deepline tools execute <id> --payload '<json>' --json --wait` - run any tool
- `deepline enrich --input <csv> --output <csv> --with '<spec>' --json` - enrich CSVs
- `deepline csv show --csv <path> --summary` - inspect CSV shape
- `deepline customer-db query --sql "<sql>" --json` - query customer DB
- `deepline billing balance --json` - check credits
- `deepline session plan/status/output/alert` - session UI updates

Always pass `--json` for structured output.

## GTM skill docs (read before executing)

Mounted at `/mnt/session/uploads/workspace/gtm-meta-skill/`:
- `SKILL.md` - routing layer (read first for any GTM task)
- `finding-companies-and-contacts.md` - prospecting
- `enriching-and-researching.md` - enrichment/waterfall patterns
- `writing-outreach.md` - outreach copy
- `recipes/` - step-by-step playbooks
- `provider-playbooks/` - per-provider details

## Rules
- NEVER read large CSVs into context. Use `deepline csv show`.
- Pilot on 1-2 rows (`--rows 0:1`) before full runs.
- Use `deepline tools search` before guessing tool IDs.
- Write outputs to `/mnt/session/outputs/` for download.
"""


def main() -> None:
    client = anthropic.Anthropic()

    existing = {}
    if CONFIG_PATH.exists():
        existing = json.loads(CONFIG_PATH.read_text())

    # Environment
    if env_id := existing.get("environment_id"):
        print(f"Reusing environment: {env_id}")
    else:
        env = client.beta.environments.create(
            name=f"deepline-managed-{os.getpid()}",
            config={"type": "cloud", "networking": {"type": "unrestricted"}},
        )
        env_id = env.id
        print(f"Created environment: {env_id}")

    tools = [
        {"type": "agent_toolset_20260401", "default_config": {"enabled": True}},
    ]

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
            description="Full-access Deepline GTM agent in Anthropic managed sandbox.",
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
