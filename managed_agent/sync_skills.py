"""Sync GTM skill docs to Anthropic Skills API.

Fetches skill docs from Deepline CDN and uploads them as an Anthropic custom skill.
The agent references the skill by ID - no file uploads needed per session.

Usage:
    python sync_skills.py          # create or update the skill
    python sync_skills.py --list   # list existing skills
"""

import json
import sys
from pathlib import Path

import anthropic
import httpx

CONFIG_PATH = Path(__file__).parent / ".agent_config.json"
SKILL_CONFIG_PATH = Path(__file__).parent / ".skill_config.json"

SKILLS_BASE = "https://code.deepline.com/.well-known/skills/gtm-meta-skill"

# Core skill docs to bundle (same list as session.py)
CORE_DOCS = [
    "SKILL.md",
    "finding-companies-and-contacts.md",
    "enriching-and-researching.md",
    "writing-outreach.md",
    "recipes/build-tam.md",
    "recipes/linkedin-url-lookup.md",
    "recipes/portfolio-prospecting.md",
    "provider-playbooks/apollo.md",
    "provider-playbooks/crustdata.md",
    "provider-playbooks/dropleads.md",
    "provider-playbooks/hunter.md",
    "provider-playbooks/leadmagic.md",
    "provider-playbooks/deepline_native.md",
    "provider-playbooks/lemlist.md",
    "provider-playbooks/instantly.md",
    "provider-playbooks/smartlead.md",
    "provider-playbooks/heyreach.md",
    "provider-playbooks/zerobounce.md",
    "provider-playbooks/exa.md",
    "provider-playbooks/firecrawl.md",
    "provider-playbooks/apify.md",
    "provider-playbooks/forager.md",
    "provider-playbooks/icypeas.md",
    "provider-playbooks/prospeo.md",
    "provider-playbooks/peopledatalabs.md",
    "provider-playbooks/ai_ark.md",
    "provider-playbooks/attio.md",
    "provider-playbooks/hubspot.md",
    "provider-playbooks/salesforce.md",
    "provider-playbooks/serper.md",
    "provider-playbooks/parallel.md",
    "provider-playbooks/deeplineagent.md",
]


def fetch_docs() -> str:
    """Fetch all skill docs from CDN and concatenate into one markdown string."""
    sections = []
    with httpx.Client(timeout=15) as http:
        for path in CORE_DOCS:
            try:
                resp = http.get(f"{SKILLS_BASE}/{path}")
                if resp.status_code == 200 and resp.text.strip():
                    sections.append(f"## {path}\n\n{resp.text}")
            except Exception as e:
                print(f"  Warning: failed to fetch {path}: {e}")
    print(f"Fetched {len(sections)}/{len(CORE_DOCS)} docs")
    return "\n\n---\n\n".join(sections)


def main() -> None:
    client = anthropic.Anthropic()

    if "--list" in sys.argv:
        skills = client.beta.skills.list()
        for s in skills.data:
            print(f"{s.id}  {getattr(s, 'name', '?')}")
        return

    # Fetch docs from CDN
    print("Fetching skill docs from CDN...")
    content = fetch_docs()
    if not content:
        sys.exit("No docs fetched")

    # Check if we already have a skill
    existing = {}
    if SKILL_CONFIG_PATH.exists():
        existing = json.loads(SKILL_CONFIG_PATH.read_text())

    skill_id = existing.get("skill_id")

    # Write content to a temp file for upload
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    if skill_id:
        print(f"Updating skill {skill_id} with new version...")
        with open(tmp_path, "rb") as f:
            version = client.beta.skills.versions.create(
                skill_id=skill_id,
                files=[("SKILL.md", f, "text/markdown")],
            )
        print(f"Created version {version.version} for skill {skill_id}")
    else:
        print("Creating new skill...")
        with open(tmp_path, "rb") as f:
            skill = client.beta.skills.create(
                display_title="Deepline GTM Skill",
                files=[("SKILL.md", f, "text/markdown")],
            )
        skill_id = skill.id
        print(f"Created skill: {skill_id}")

    import os
    os.unlink(tmp_path)

    # Save config
    config = {"skill_id": skill_id}
    SKILL_CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"Saved to {SKILL_CONFIG_PATH}")

    # Update the agent to reference this skill
    if CONFIG_PATH.exists():
        agent_config = json.loads(CONFIG_PATH.read_text())
        agent_id = agent_config.get("agent_id")
        agent_version = agent_config.get("agent_version")
        if agent_id:
            print(f"Updating agent {agent_id} to include skill...")
            agent = client.beta.agents.update(
                agent_id=agent_id,
                version=agent_version,
                skills=[
                    {"type": "custom", "skill_id": skill_id, "version": "latest"},
                ],
            )
            agent_config["agent_version"] = agent.version
            CONFIG_PATH.write_text(json.dumps(agent_config, indent=2))
            print(f"Agent updated to v{agent.version} with skill {skill_id}")


if __name__ == "__main__":
    main()
