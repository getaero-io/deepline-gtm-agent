# AgentMail Inbox For Deepline GTM Agent

AgentMail is the agent's email identity and inbound routing channel. It is not the primary outbound system.

Primary interfaces:

1. Telegram: fast operator chat.
2. Deepline Session UI: GTM execution plans, progress, logs, usage, and output lineage.
3. AgentMail: agent-owned inbox for receiving context, creating drafts, and routing replies.

## Setup

Install the CLI on the Sprite:

```bash
npm install -g agentmail-cli
```

Start agent sign-up:

```bash
agentmail agent sign-up \
  --human-email jai@deepline.ai \
  --username deepline-gtm-agent \
  --format json
```

AgentMail sends a 6-digit OTP to the human email. Verify it:

```bash
export AGENTMAIL_API_KEY="<api-key-from-sign-up>"
agentmail agent verify --otp-code "<otp-code>"
```

Create or reuse the inbox:

```bash
agentmail inboxes create \
  --display-name "Deepline GTM Agent" \
  --username deepline-gtm-agent \
  --domain agentmail.to \
  --format json
```

## Hermes Profile Env

Store secrets only in:

```text
/home/sprite/.hermes/profiles/deeplinegtm/.env
```

Required:

```bash
AGENTMAIL_API_KEY=
AGENTMAIL_INBOX_ID=
AGENTMAIL_EMAIL=
```

Optional:

```bash
AGENTMAIL_ORGANIZATION_ID=
AGENTMAIL_ALLOWED_SEND_DOMAINS=
```

## Operating Rules

- Draft-first. Do not send email without approval.
- Use AgentMail for inbound messages, thread inspection, and draft creation.
- Use Deepline for GTM provider execution, enrichment, logging, usage, and output lineage.
- Use Gmail only when sending as Jai or using existing Deepline customer email context.
- Keep AgentMail send tools disabled or approval-gated in MCP.
- Never use AgentMail to run unsupervised outbound sequences.

## First Safe Tests

```bash
agentmail inboxes list --format json
agentmail inboxes:threads list --inbox-id "$AGENTMAIL_INBOX_ID" --format json
```

Draft-only test:

```bash
agentmail inboxes:drafts create \
  --inbox-id "$AGENTMAIL_INBOX_ID" \
  --to jai@deepline.ai \
  --subject "Deepline GTM Agent inbox test" \
  --text "Draft-only AgentMail test from deeplinegtm." \
  --format json
```

If the installed CLI does not expose `inboxes:drafts create`, use the AgentMail MCP `create_draft` tool after connecting the hosted MCP server with read/list/create-draft scope.
