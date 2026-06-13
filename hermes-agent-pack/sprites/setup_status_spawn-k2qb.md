# Setup Status: spawn-k2qb

Last updated: 2026-06-08

## Completed

- Confirmed Sprite exists: `spawn-k2qb`.
- Confirmed Hermes installed.
- Created Sprite checkpoint: `v1`.
- Updated Hermes from `v0.14.0` to `v0.16.0 (2026.6.5)`.
- Uploaded this repo to:

```text
/home/sprite/deepline-hermes-repo
```

- Installed Hermes profile/skills:

```text
/home/sprite/.hermes/profiles/deeplinegtm/skills/deepline-gtm-agent/SKILL.md
/home/sprite/.hermes/profiles/deeplinegtm/skills/deepline-sales-workflows/SKILL.md
/home/sprite/.hermes/profiles/deeplinegtm/skills/deepline-marketing-content-agent/SKILL.md
/home/sprite/.hermes/profiles/deeplinegtm/skills/deepline-marketing-campaign-agent/SKILL.md
/home/sprite/.hermes/profiles/deeplinegtm/skills/deepline-marketing-proof-agent/SKILL.md
```

- Added scoped filesystem MCP:

```text
deepline-filesystem -> /home/sprite/deepline-hermes-repo
```

- Pruned filesystem MCP tool exposure in `~/.hermes/config.yaml`.
- Created dedicated Hermes profile:

```text
deeplinegtm
```

- Set the `deeplinegtm` terminal working directory to:

```text
/home/sprite/deepline-hermes-repo
```

- Installed the Deepline SOUL file for the `deeplinegtm` profile.
- Set operating posture: Deepline-native CLI/API/session tooling is the primary GTM access, logging, and observability layer; Hermes MCPs are sidecars only.
- Set `GATEWAY_ALLOW_ALL_USERS=false` in the `deeplinegtm` profile env.
- Set `security.redact_secrets=true` in the `deeplinegtm` profile config.
- Replaced the profile launcher so `deeplinegtm ...` always starts from:

```text
/home/sprite/deepline-hermes-repo
```

- Created starter working directories:

```text
/home/sprite/deepline-hermes-repo/output/gtm_agent
/home/sprite/deepline-hermes-repo/output/marketing_content
/home/sprite/deepline-hermes-repo/output/marketing_campaigns
/home/sprite/deepline-hermes-repo/output/marketing_proof
/home/sprite/deepline-hermes-repo/output/account_research
/home/sprite/deepline-hermes-repo/context/source_notes
```
- Added Telegram helper:

```text
/home/sprite/deepline-hermes-repo/scripts/configure_telegram_env.sh
```

- Added Telegram primary-interface docs:

```text
/home/sprite/deepline-hermes-repo/hermes/telegram_primary_interface.md
```

- Installed AgentMail CLI and created the agent inbox:

```text
deepline-gtm-agent@agentmail.to
```

- Stored AgentMail secrets in the `deeplinegtm` profile env only:

```text
/home/sprite/.hermes/profiles/deeplinegtm/.env
```

- Sent AgentMail verification email to `jai@deepline.ai`; account verification is waiting on the OTP.
- Added research-backed setup docs:

```text
/home/sprite/deepline-hermes-repo/docs/research_backed_setup.md
/home/sprite/deepline-hermes-repo/hermes/agentmail_primary_inbox.md
```

## Smoke Tests Passed

All tests ran through the `deeplinegtm` profile on `spawn-k2qb`.

- Read `HERMES.md` and claims context, then summarized role/exclusions/approval gates.
- Generated draft post-call follow-up for Clay vs Deepline / Claude Code GTM workflow.
- Generated LinkedIn draft about "the agent is not the moat"; saved to:

```text
/home/sprite/deepline-hermes-repo/output/linkedin_agent_not_the_moat.md
```

- Generated account research brief for a technical RevOps agency considering Clay alternatives; saved to:

```text
/home/sprite/deepline-hermes-repo/output/account_brief_technical_revops_agency_clay_alt.md
```

- Correctly blocked flagged claims:
  - "65% market coverage free"
  - "install in under 2 minutes"
- Confirmed `deeplinegtm -z "run pwd"` now launches from `/home/sprite/deepline-hermes-repo` through the repo-aware wrapper.
- Confirmed AgentMail inbox list access returns `deepline-gtm-agent@agentmail.to`.

Enabled tools:

- `read_text_file`
- `read_multiple_files`
- `write_file`
- `edit_file`
- `create_directory`
- `list_directory`
- `list_directory_with_sizes`
- `directory_tree`
- `search_files`
- `get_file_info`
- `list_allowed_directories`

## Optional Sidecar / Needs Browser Auth

Composio remote MCP reached OAuth but did not persist because first connection/tool discovery timed out in the headless Sprite flow.

This is not blocking the core Deepline GTM agent path. Deepline itself should own provider access, workflow execution, logs, usage, and output lineage. Composio is only needed for scoped SaaS sidecar actions that Deepline should not own.

Manual auth path:

```bash
hermes mcp add composio --url https://connect.composio.dev/mcp --auth oauth
```

When the OAuth URL appears, complete it in a browser where the callback can reach the Sprite-side local listener, or use a supported remote/OAuth setup path.

## Current MCP Catalog On Sprite

After Hermes update, the available Nous catalog entries were:

- `linear`
- `n8n`

Neither was installed because the Deepline day-one workflows need Deepline-native execution plus scoped filesystem more than Linear/n8n, and n8n requires separate workflow credentials/config to be useful.

## Known Remaining Constraints

- The remote repo on `spawn-k2qb` is an uploaded working directory, not a git checkout.
- Composio still requires OAuth completion before optional SaaS sidecar tools are available.
- Telegram still requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USERS`.
- AgentMail still requires the OTP sent to `jai@deepline.ai`.
- Telegram bot token creation still requires Jai's Telegram account via `@BotFather`; the verification script is installed at `scripts/verify_telegram_env.sh`.
- The Sprite shell does not expose `systemctl`, `launchctl`, `s6-svc`, `sv`, or `supervisorctl`; use foreground gateway mode unless Sprites provides another supervisor.

## Next Recommended Action

Set Telegram credentials:

```bash
cd /home/sprite/deepline-hermes-repo
TELEGRAM_BOT_TOKEN="<botfather-token>" TELEGRAM_ALLOWED_USERS="<jai-telegram-user-id>" \
  bash scripts/configure_telegram_env.sh
deeplinegtm gateway run
```

Verify AgentMail after receiving the OTP:

```bash
cd /home/sprite/deepline-hermes-repo
set -a; source /home/sprite/.hermes/profiles/deeplinegtm/.env; set +a
AGENTMAIL_OTP_CODE="<otp-code>" bash scripts/setup_agentmail.sh deeplinegtm
```

Then message the Telegram bot:

```text
/start
/new
Read HERMES.md and summarize your Deepline operating rules.
```

For CLI setup, start Hermes on the Sprite and paste:

```text
prompts/00_seed_hermes.md
```

Then run:

```text
prompts/01_gtm_agent.md
prompts/02_marketing_agents.md
prompts/03_connector_setup.md
```
