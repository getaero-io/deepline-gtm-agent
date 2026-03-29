# Setup Guide

Two paths: **CLI** (fast, scriptable, good for agents and devs) and **UI** (step-by-step, good for anyone).

---

## Railway

### CLI setup

```bash
# Install Railway CLI
npm install -g @railway/cli

# Authenticate
railway login

# Link to existing project or create new one
railway init                  # new project
# or
railway link                  # link to existing

# Set all required env vars in one shot
railway variables set \
  DEEPLINE_API_KEY="dlp_..." \
  OPENAI_API_KEY="sk-..." \
  LLM_MODEL="openai:gpt-4o" \
  PORT="8000"

# Deploy
railway up --detach

# Get your public domain
railway domain
```

Your domain will look like `your-app-name.up.railway.app`. You'll need it for the Slack setup below.

To update env vars after deploying:
```bash
railway variables set SLACK_BOT_TOKEN="xoxb-..." SLACK_SIGNING_SECRET="..."
railway up --detach   # redeploy to pick up new vars
```

To tail logs:
```bash
railway logs
```

---

### UI setup

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Connect your fork of this repo
3. Railway auto-detects the `Dockerfile` and builds it
4. Go to your service → **Variables** → add:
   - `DEEPLINE_API_KEY` — from [code.deepline.com](https://code.deepline.com)
   - `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
   - `LLM_MODEL` — e.g. `openai:gpt-4o` or `anthropic:claude-opus-4-6`
   - `PORT` — `8000`
5. Go to **Settings** → **Networking** → **Generate Domain** → copy the URL

---

## Slack

You need three things: a **bot token** (`xoxb-...`), a **signing secret**, and the **events webhook** pointing at your Railway URL.

### CLI setup (fast path — uses the Slack manifest)

```bash
# Install Slack CLI
curl -fsSL https://downloads.slack-edge.com/slack-cli/install.sh | bash

# Authenticate
slack login

# Create the app from the manifest in this repo
# First update the two placeholder URLs in slack-manifest.json:
sed -i '' 's|YOUR_RAILWAY_DOMAIN|your-app.up.railway.app|g' slack-manifest.json

# Create app from manifest
slack app create --manifest slack-manifest.json

# Install to your workspace
slack app install

# Get the bot token and signing secret
slack app list        # shows your app ID
slack app credentials # shows client ID, client secret, signing secret
```

After the app is created and installed, get the bot token from the Slack UI:
`api.slack.com/apps` → your app → **OAuth & Permissions** → copy `xoxb-...`

Then set both in Railway:
```bash
railway variables set \
  SLACK_BOT_TOKEN="xoxb-..." \
  SLACK_SIGNING_SECRET="..."
railway up --detach
```

---

### UI setup (step by step)

**Step 1 — Create the app**

Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App**.

Two options:
- **From manifest** (faster) — paste the contents of `slack-manifest.json` (after replacing `YOUR_RAILWAY_DOMAIN`). This pre-fills all scopes and event subscriptions.
- **From scratch** — pick a name and workspace, then configure manually below.

---

**Step 2 — Add bot scopes** *(skip if you used the manifest)*

**OAuth & Permissions** → **Bot Token Scopes** → Add:
- `chat:write`
- `app_mentions:read`
- `im:read` + `im:history`
- `channels:read`
- `channels:history`
- `groups:history`
- `mpim:history`

---

**Step 3 — Add redirect URL** *(for the OAuth install flow)*

**OAuth & Permissions** → **Redirect URLs** → Add:
```
https://<your-railway-domain>/slack/oauth_redirect
```

---

**Step 4 — Enable Event Subscriptions**

**Event Subscriptions** → toggle **Enable Events** → paste the Request URL:
```
https://<your-railway-domain>/slack/events
```

Slack will send a verification challenge — the server responds automatically. You should see **Verified ✓** within a few seconds.

Under **Subscribe to bot events**, add:
- `app_mention`
- `message.im`

Click **Save Changes**.

---

**Step 5 — Install to workspace**

**OAuth & Permissions** → **Install to Workspace** → Authorize.

You'll be redirected to `https://<your-railway-domain>/slack/oauth_redirect`. The page will display your `SLACK_BOT_TOKEN`. Copy it.

---

**Step 6 — Get the signing secret**

**Basic Information** → **App Credentials** → copy **Signing Secret**.

---

**Step 7 — Set env vars in Railway**

```bash
railway variables set \
  SLACK_BOT_TOKEN="xoxb-..." \
  SLACK_SIGNING_SECRET="..."
railway up --detach
```

Or in the Railway UI: your service → **Variables** → add both values → **Deploy**.

---

**Step 8 — Test**

DM `@Deepline GTM Agent` in Slack:

```
Find 3 VP of Sales at B2B SaaS companies, 100–500 employees, US
```

The bot replies in-thread and maintains conversation history per thread.

---

## Verify everything is working

```bash
# Health check
curl https://<your-railway-domain>/health

# Expected response:
# {"status":"ok","agent":"deepline-gtm-agent","slack":"configured","skills":"6 docs loaded"}
```

If `slack` shows `"not configured"`, `SLACK_BOT_TOKEN` isn't set. If `skills` shows `"not loaded"`, the server can't reach `code.deepline.com` — check `DEEPLINE_API_KEY`.

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | From [code.deepline.com](https://code.deepline.com) |
| `OPENAI_API_KEY` | One of these | OpenAI key |
| `ANTHROPIC_API_KEY` | One of these | Anthropic key |
| `LLM_MODEL` | Yes | e.g. `openai:gpt-4o`, `anthropic:claude-opus-4-6` |
| `PORT` | Yes | `8000` |
| `SLACK_BOT_TOKEN` | For Slack | `xoxb-...` from OAuth & Permissions |
| `SLACK_SIGNING_SECRET` | For Slack | From Basic Information → App Credentials |
| `SLACK_CLIENT_ID` | For OAuth flow | From Basic Information → App Credentials |
| `SLACK_CLIENT_SECRET` | For OAuth flow | From Basic Information → App Credentials |
| `API_KEY` | Optional | Protect `/chat` endpoints with bearer auth |
| `CORS_ORIGINS` | Optional | Comma-separated allowed origins (default: `*`) |
