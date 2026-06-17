# Deepline GTM Eve Agent

Eve reference implementation for the Deepline GTM agent. This app keeps Deepline as the GTM execution backend and uses Eve for durable agent sessions, local development, evals, and Vercel deployment.

The existing Python/FastAPI broker remains the default runtime in the repository. Use this package when you want the faster Eve deployment path or want to validate Deepline GTM behavior through Eve evals.

## Requirements

- Node.js 24
- A Deepline API key from https://code.deepline.com
- One model path:
  - Vercel AI Gateway via `eve link` or `AI_GATEWAY_API_KEY`
  - A direct provider key such as `ANTHROPIC_API_KEY`

## Configure

```bash
cd eve_agent
npm install
cp .env.example .env
```

Set at least:

```bash
DEEPLINE_API_KEY=dlp_...
```

For local model access, either link Eve to Vercel AI Gateway:

```bash
npx eve link
```

or set a direct key supported by Eve, for example:

```bash
ANTHROPIC_API_KEY=sk-ant-...
EVE_MODEL=anthropic/claude-sonnet-4.6
```

## Run Locally

```bash
npm run dev
```

Eve serves the local agent over HTTP. In another terminal, run:

```bash
npm run smoke -- --host http://127.0.0.1:3000
```

The smoke script checks Eve health, creates a session, opens the session stream, and waits for a completed or waiting event.

## Test

```bash
npm test
npm run typecheck
npm run build
```

Run deterministic evals with:

```bash
npm run eval -- smoke
npm run eval -- workflow-presets
```

Eval execution requires model credentials. Without AI Gateway or a provider key, Eve will compile but model-backed evals will fail at runtime.

## Deploy To Vercel

```bash
cd eve_agent
npm install
npx eve link
npx vercel
```

Set production environment variables in Vercel:

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | Deepline v2 API key |
| `DEEPLINE_API_BASE_URL` | Optional | Defaults to `https://code.deepline.com` |
| `AI_GATEWAY_API_KEY` | Usually | Required unless using Vercel OIDC or another configured model path |
| `ANTHROPIC_API_KEY` | Optional | Direct-provider local or deployed fallback |
| `EVE_MODEL` | Optional | Overrides Eve's default model |

After deployment, verify the live URL:

```bash
npm run smoke -- --host https://<your-vercel-url>
```

## Parity Surface

The Eve port preserves the important Deepline GTM behavior:

- full Deepline v2 agent/chat streaming through the `deepline_chat` tool
- direct Deepline v2 tool execution through `deepline_execute_tool`
- GTM guidance around evidence, uncertainty, CRM safety, and bounded action
- workflow presets for enrichment, account digests, support, web research, bounded tool action, closed-loop GTM, and Snowflake query agents
- deterministic eval coverage for smoke behavior, workflow presets, enrichment guidance, account research, and approval rules

Slack remains on the Python broker for now. The Eve package is structured so an Eve Slack channel can be added later without blocking the faster Vercel deployment path.
