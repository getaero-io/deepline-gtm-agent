# Eve Additive Port Design

## Goal

Add an Eve-based Deepline GTM agent implementation alongside the existing Python/FastAPI broker, prove full functional parity end to end, and make deployment faster without changing the current default runtime until the Eve path passes parity gates.

## Context

The current repo is a Python package and FastAPI broker. The recommended runtime is `managed_agent/server.py`, which exposes REST, web chat, Slack, workflow preset discovery, and streaming while Deepline v2 owns tool routing, provider credentials, billing, native chat, and execution.

Eve is a filesystem-first TypeScript framework for durable agents. It discovers capabilities from an `agent/` directory, runs durable sessions, exposes a stable HTTP session API, supports channels, typed tools, approval gates, state, evals, and Vercel deployment.

The port should not replace the existing broker yet. Eve is beta, requires Node 24, and has a different HTTP/streaming contract than the repo's current `/chat` and `/chat/stream` endpoints. We need an additive implementation that can be evaluated without disrupting current users.

## Chosen Approach

Create a sibling Eve app under `eve_agent/`.

The Python broker remains the default documented path. The Eve app becomes a reference implementation and future default candidate once it passes parity and deployment checks.

## Non-Goals

- Do not remove or rewrite `managed_agent/server.py`.
- Do not change the existing Python package default behavior.
- Do not require local Deepline CLI state.
- Do not expose Deepline, Slack, CRM, or model credentials to the model.
- Do not make Slack the first parity gate; prove Eve HTTP/web first, then add Slack via Vercel Connect.

## Architecture

The Eve app owns the agent runtime shell, durable sessions, local/dev HTTP session API, evals, and Vercel deployment.

Deepline remains the GTM execution backend. Eve tools call Deepline v2 APIs through `DEEPLINE_API_KEY`; Deepline continues to own provider execution, billing, integration credentials, native GTM tool routing, and provider-specific workflows.

Initial tree:

```text
eve_agent/
├── package.json
├── tsconfig.json
├── agent/
│   ├── agent.ts
│   ├── instructions.md
│   ├── channels/
│   │   └── eve.ts
│   ├── lib/
│   │   ├── deepline.ts
│   │   ├── workflow-presets.ts
│   │   └── guidance.ts
│   └── tools/
│       ├── deepline_chat.ts
│       ├── deepline_execute_tool.ts
│       ├── list_workflow_presets.ts
│       └── get_workflow_preset.ts
└── evals/
    ├── evals.config.ts
    ├── smoke.eval.ts
    ├── workflow-presets.eval.ts
    └── parity/
        ├── enrichment.eval.ts
        ├── research.eval.ts
        └── approval-guidance.eval.ts
```

## Runtime Behavior

`agent/instructions.md` carries the stable GTM rules from the Python broker:

- source, verify, bound tools, draft/recommend, approval, write back, learn
- never invent contacts, emails, URLs, company facts, or CRM record IDs
- ask before outreach, CRM writeback, task creation, sequence enrollment, or data mutation
- prefer Deepline native workflows and plays over provider spraying
- use pilot/sample approval before bulk prospecting
- keep Snowflake and warehouse workflows read-only until explicitly approved

`deepline_chat` sends a prompt to Deepline native `deeplineagent`. It should accept optional `messages`, `enabledToolIds`, `maxToolCalls`, and `model` so parity tests can cover bounded workflows. It returns a final text reply for the Eve model and preserves enough metadata for evals and debugging.

`deepline_execute_tool` executes a single v2 tool route at `/api/v2/integrations/{toolId}/execute`. It is for specific direct operations and smoke tests, not broad provider loops.

Workflow preset tools expose the same starter workflow data currently served by `managed_agent/workflow_presets.py`.

## HTTP and Streaming Compatibility

Eve's canonical HTTP API is:

- `GET /eve/v1/health`
- `POST /eve/v1/session`
- `POST /eve/v1/session/:sessionId`
- `GET /eve/v1/session/:sessionId/stream`

The first implementation should use this native Eve contract rather than reproducing `/chat/stream`. A later compatibility adapter can be added only if existing consumers need a drop-in `/chat` endpoint.

Parity evals must verify Eve NDJSON streams reach completion and include tool-call/action events when tools are used.

## Deployment

Use Vercel as the preferred Eve deployment target because Eve builds directly into Vercel output and exposes session routes without maintaining a separate FastAPI/Railway service.

The fastest deployment path should be:

```bash
cd eve_agent
npm install
npm run build
vercel deploy
```

Required environment:

- `DEEPLINE_API_KEY`
- one model credential path: preferably Vercel AI Gateway through project OIDC, or direct provider key for the configured model

Production route auth must fail closed. The initial Eve HTTP channel should allow local development and trusted Vercel/OIDC calls, with explicit docs for public browser auth if needed.

## Parity Gates

The Eve implementation is not considered complete until these pass:

- Fresh clone setup works with documented commands.
- Local `npm run dev` starts Eve.
- `GET /eve/v1/health` succeeds locally.
- `POST /eve/v1/session` accepts a GTM prompt.
- `GET /eve/v1/session/:sessionId/stream` streams through completion.
- Deepline requests use `DEEPLINE_API_KEY` and no local CLI state.
- Contact enrichment prompt reaches Deepline and returns a meaningful sourced result or credential/data-coverage error.
- Account research prompt reaches Deepline and returns source-backed output.
- Bulk prospect/list prompt includes pilot/sample and approval guidance.
- Agent/workflow prompt includes source, verify, bound tools, approval, writeback, and learn guidance.
- Snowflake prompt includes read-only SQL and approval-before-writeback guidance.
- Workflow preset listing and detail tools match the existing Python preset content.
- Existing Python tests still pass.
- Eve evals pass locally, and can target a deployed Vercel URL.

## Rollout

Phase 1: Add Eve app and local smoke evals.

Phase 2: Add parity evals against representative existing prompts.

Phase 3: Add Vercel deployment docs and production smoke checklist.

Phase 4: Add Slack via Eve/Vercel Connect after HTTP parity passes.

Phase 5: Decide whether to make Eve the default runtime after repeated parity runs and deployment validation.

## Research Notes

Eve's launch positioning emphasizes that an agent is a directory of files with durable execution, sandboxed compute, human-in-the-loop approvals, subagents, channels, and evals built in. This aligns with the current repo's positioning around bounded tools, approval loops, workflow presets, and production GTM agent safety.

The main migration risk is contract mismatch: the repo currently exposes FastAPI `/chat` and `/chat/stream` while Eve exposes durable session routes and NDJSON events. The additive approach isolates that risk.

