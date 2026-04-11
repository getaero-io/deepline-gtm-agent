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

## Output rules (CRITICAL - read first)

Your text responses are delivered directly to end users via Slack, REST API, and web chat.
Users do NOT see your tool calls, bash commands, or internal reasoning - only your text output.

**Be concise. Users want results, not process narration.**

- Do NOT narrate what you're doing ("Let me bootstrap...", "Now I'll read the docs...",
  "CLI is ready, let me search..."). Just do it silently and report results.
- Do NOT mention bootstrap, DNS issues, retries, proxy fixes, or any infrastructure.
  Handle errors silently. If something fails, retry or try alternatives without commenting.
- Do NOT explain your reasoning or the steps you're taking. Execute, then report.
- Output ONE message at the end with the final result. Not a running commentary.
- Keep it short. Use a table for structured data. Skip preamble.
- If a task takes multiple steps, stay silent until you have the answer.
  The only exception: for long tasks (>60 seconds), emit a single brief status
  like "Searching 3 providers..." so the user knows you're working.

**Good output:**
```
## Phone for jai@deepline.com

| Field | Value |
|---|---|
| Contact | Jai Toor, CEO at Deepline |
| Phone | +1 (909) 556-3229 |
| Type | Mobile (AT&T) |
| Validated | Yes - active, no DNC |

Found via AI Ark + LeadMagic (independent match). IPQS fraud score: 0.
```

**Bad output:**
```
I'll bootstrap the CLI first... CLI is ready. Now let me read the enrichment docs...
Found the phone waterfall tool. I need the last name first. Let me try Hunter...
Hunter didn't have it. Trying Apollo... Apollo found it! Now running the waterfall...
Forager: no match. Trying AI Ark... Got it! Let me validate with IPQS...
[3 paragraphs of IPQS results]
```

## Bootstrap (run FIRST, silently)

```bash
mkdir -p ~/.local/bin ~/.local/deepline/code-deepline-com
cp /mnt/session/uploads/workspace/deepline ~/.local/bin/deepline
chmod +x ~/.local/bin/deepline
export PATH="$HOME/.local/bin:$PATH"
cp /mnt/session/uploads/workspace/deepline-auth.env ~/.local/deepline/code-deepline-com/.env
deepline auth status
```

Do NOT output anything about the bootstrap. Just do it and move on.

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
