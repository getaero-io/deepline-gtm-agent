# Telegram Primary Interface Setup

Hermes v0.16 uses the messaging gateway for Telegram.

## Required Values

Create a Telegram bot with `@BotFather`:

```text
/newbot
Deepline GTM Agent
deepline_gtm_agent_bot
```

Then get Jai's numeric Telegram user ID from `@userinfobot` or `@getmyid_bot`.

BotFather token creation requires Jai's Telegram account. An agent cannot mint this token without completing Telegram account auth in a browser or Telegram client.

Set these in the `deeplinegtm` Hermes profile:

```bash
deeplinegtm config env-path
```

Add:

```bash
TELEGRAM_BOT_TOKEN=<botfather-token>
TELEGRAM_ALLOWED_USERS=<jai-numeric-user-id>
GATEWAY_ALLOW_ALL_USERS=false
```

Do not use `GATEWAY_ALLOW_ALL_USERS=true` for this agent.

## Configure And Verify

```bash
cd /home/sprite/deepline-hermes-repo
TELEGRAM_BOT_TOKEN="<botfather-token>" \
TELEGRAM_ALLOWED_USERS="<jai-numeric-user-id>" \
  bash scripts/configure_telegram_env.sh

bash scripts/verify_telegram_env.sh deeplinegtm
```

## Start Gateway

Foreground test:

```bash
deeplinegtm gateway run
```

Production service:

```bash
deeplinegtm gateway install
deeplinegtm gateway start
deeplinegtm gateway status
```

## First Telegram Commands

In Telegram, message the bot:

```text
/start
/new
Read /home/sprite/deepline-hermes-repo/HERMES.md and summarize your Deepline operating rules.
```

Then:

```text
Run prompts/00_seed_hermes.md. Do not connect tools or send anything externally.
```

## Telegram Use Rules

- Use Telegram for command and review.
- Put longer artifacts in repo files under `output/`.
- Use `/new` when changing from sales to marketing or from setup to execution.
- Keep all sends/publishes/CRM writes approval-gated.
