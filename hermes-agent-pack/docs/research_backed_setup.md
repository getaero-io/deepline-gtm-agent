# Research-Backed Hermes GTM Setup

Last updated: 2026-06-08.

Inputs:

- last30days research on Hermes agent setup, GTM engineering, Andrej Karpathy / AI engineering authority discussion.
- Hermes docs for integrations, tools/toolsets, web dashboard, MCP, messaging gateway, and Tool Gateway.
- AgentMail docs for agent sign-up, CLI, inboxes, MCP, drafts, webhooks, and WebSockets.

## What The Recent Signal Says

The useful pattern is not "connect every tool." It is:

1. Give the agent a small, explicit context pack.
2. Give it one primary execution system with logs and lineage.
3. Expose a thin operator interface.
4. Add sidecar tools only after the workflow proves useful.

For Deepline GTM, that means:

- Hermes is the interface and skill/profile layer.
- Deepline is GTM execution, provider routing, logs, usage, Session UI, and output lineage.
- Telegram is the fastest operator loop.
- AgentMail is the agent-owned inbox.
- MCPs are scoped sidecars, not the core GTM system.

## Authority-Aligned Principles

Recent Karpathy-adjacent discussion keeps pointing at context engineering and spec quality: the agent gets better when the operator improves the context, constraints, and execution loop. In this repo, that maps to:

- small durable context files instead of full transcript ingestion
- explicit claims/exclusions
- one workflow plan before execution
- one-row pilots before bulk runs
- read-after-write and log inspection
- tool routing to prevent token and tool bloat

## Required Integrations

| Integration | Priority | Role | Setup State |
| --- | --- | --- | --- |
| Deepline CLI/API | P0 | GTM execution, enrichment, logs, usage, output lineage | Installed on `spawn-k2qb` |
| Telegram gateway | P0 | Primary operator chat | Waiting for bot token + allowed user ID |
| Scoped filesystem MCP | P0 | Read/write this repo and outputs only | Installed and tested |
| AgentMail | P1 | Agent-owned inbox, inbound routing, draft handling | CLI install/sign-up started; OTP required |
| Hermes dashboard | P1 | Sessions, logs, env, toolsets, MCP, gateway, usage | Recommended when Sprite exposes a safe URL |
| Nous Portal / Tool Gateway | P1 | Hermes web/search/browser/TTS/image without separate keys | Optional but recommended |
| GitHub | P2 | Repo/PR workflows | Add only when this repo has a remote |
| Slack | P2 | Search selected GTM/customer channels, draft replies | Sidecar only |
| Google Drive/Sheets | P2 | Read approved files, export drafts | Sidecar only |
| HubSpot | P2 | Search/propose CRM updates | Sidecar only |
| Gmail | P2 | Draft as Jai where required | Sidecar only; never send unsupervised |
| Composio | P3 | OAuth sidecar when app MCPs are easier than direct setup | Optional, not core |

## Credential-Gated Setup Notes

- Telegram: create the bot token in Jai's Telegram account with `@BotFather`, then run `scripts/configure_telegram_env.sh` and `scripts/verify_telegram_env.sh`.
- AgentMail: inbox exists and list/thread access works; verification waits on the OTP sent to `jai@deepline.ai`.
- Hermes dashboard: run `deeplinegtm dashboard --host 127.0.0.1 --port 9119 --no-open` and reach it through a private tunnel/proxy. Do not run it with `--insecure` on a public interface.
- Nous Portal / Tool Gateway: complete OAuth through Hermes setup/dashboard when a browser session is available. This is optional for the GTM run because Deepline owns GTM provider access.
- Hosted MCPs: only add after a manual pruning pass. Avoid enabling send/delete/admin tools by default.

## Recommended Skills

Keep the enabled skill set small. Use one general GTM operator and bounded subagent skills:

- `deepline-gtm-agent`
- `deepline-sales-workflows`
- `deepline-marketing-content-agent`
- `deepline-marketing-campaign-agent`
- `deepline-marketing-proof-agent`
- `deepline-proof-guard`
- `deepline-account-research`
- `deepline-crm-hygiene`
- `deepline-agentmail-inbox`
- `deepline-workflow-spec`

Do not enable broad generic skills until the operator asks for them.

## Day-One GTM Workflows

1. Telegram: "research this account and draft a first-touch angle."
2. Deepline Session UI: run one-row enrichment and show logs/usage/output.
3. AgentMail: receive inbound context and create a draft reply.
4. GTM agent: route a post-call follow-up to the sales-workflows subagent and return an action table.
5. Marketing content agent: transcript excerpt to LinkedIn draft, then marketing proof agent for claims review.

## Stop Conditions

Stop for approval before:

- sending email
- publishing content
- modifying CRM
- running bulk enrichment
- enabling broad SaaS MCP scopes
- bypassing Deepline for GTM provider execution Deepline can run and observe

## Sources Used

- last30days saved raw report: `~/Documents/Last30Days/hermes-agent-setup-gtm-engineering-ai-engineering-authoritie-raw.md`
- Hermes integrations docs: https://hermes-agent.nousresearch.com/docs/integrations/
- Hermes tools/toolsets docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/tools/
- Hermes dashboard docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
- AgentMail quickstart: https://docs.agentmail.to/quickstart
- AgentMail MCP docs: https://docs.agentmail.to/integrations/mcp
- AgentMail CLI docs: https://docs.agentmail.to/integrations/cli
