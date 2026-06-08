# Sprite: spawn-k2qb

User-provided instance:

```text
spawn-k2qb
```

Assumption: Hermes is already installed.

## Goal

Turn `spawn-k2qb` into a Deepline GTM agent workspace with:

- pruned Deepline context
- one primary general Deepline GTM Hermes agent
- bounded sales workflow subagent skills
- separate marketing specialist agents for content, campaigns, and proof
- conservative MCP setup
- draft-only first workflows
- connector policy encoded before any tool use

## Setup Steps

```bash
sprite use spawn-k2qb
sprite exec -s spawn-k2qb -- bash -lc 'hermes doctor || true'
sprite exec -s spawn-k2qb -- bash -lc 'mkdir -p ~/deepline-hermes-repo'
```

Then copy or clone this repo into the Sprite.

Inside the Sprite:

```bash
cd ~/deepline-hermes-repo
bash scripts/install_hermes_mcps.sh
```

## First Hermes Prompt

Use:

```text
prompts/00_seed_hermes.md
```

Then:

```text
prompts/01_gtm_agent.md
prompts/02_marketing_agents.md
prompts/03_connector_setup.md
```

## Do Not Do On Day One

- connect the full transcripts folder
- allow Hermes to send emails
- allow Hermes to bulk update CRM
- expose all filesystem paths
- expose all MCP tools
- use private transcript quotes externally
- run autonomous outbound
