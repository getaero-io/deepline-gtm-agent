---
name: deepline-agentmail-inbox
description: Use for Deepline GTM AgentMail workflows: inbox triage, inbound context capture, reply drafting, thread summaries, and safe email identity management. Draft-only by default.
---

# Deepline AgentMail Inbox Skill

## Trigger

Use this when the user asks for:

- checking the agent inbox
- summarizing inbound email threads
- drafting a reply from the Deepline GTM agent
- routing inbound requests into Deepline workflows
- creating or verifying an agent-owned inbox

## Required Context

Read first:

- `context/deepline_gtm_context.md`
- `context/claims_and_exclusions.md`
- `context/jai_voice_and_copy_rules.md`
- `rules/agent_operating_rules.md`
- `hermes/agentmail_primary_inbox.md`

## Rules

- AgentMail is an identity and inbound routing channel, not an unsupervised outbound system.
- Never send or schedule email without explicit approval.
- Prefer draft creation over send.
- Use Deepline for GTM data execution, enrichment, logs, usage, and output lineage.
- Use AgentMail only for inbox/thread/message/draft operations.
- Never expose `AGENTMAIL_API_KEY` in chat, Markdown, logs, or committed files.

## Workflow

1. Identify the inbox job: list inboxes, read thread, summarize, draft reply, or route work.
2. Confirm `AGENTMAIL_INBOX_ID` and `AGENTMAIL_EMAIL` are configured.
3. Read only the relevant thread/message.
4. If GTM data is needed, start a Deepline Session UI plan and use Deepline-native tools.
5. Draft the response.
6. Add claims that need review.
7. Ask for explicit approval before send or scheduling.

## Output Pattern

Thread summary:

- sender
- ask
- context
- suggested owner
- recommended next action
- risk / approval note

Reply draft:

- subject
- body
- source context
- claims needing review
- send approval required
