# Eve Additive Port Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an Eve-based Deepline GTM agent under `eve_agent/`, prove parity with the existing Python broker, and provide a faster Vercel deployment path without changing the current default runtime.

**Architecture:** Keep the existing Python/FastAPI broker intact. Add a sibling TypeScript Eve app whose tools call Deepline v2 with `DEEPLINE_API_KEY`; Eve owns durable sessions, local HTTP, evals, and Vercel deployment while Deepline remains the GTM execution backend.

**Tech Stack:** Node 24, npm, TypeScript, Eve, Vercel AI Gateway or direct model key, Zod, Deepline v2 REST API, Eve evals, pytest for existing Python parity checks.

---

### Task 1: Add Eve App Skeleton

**Files:**
- Create: `eve_agent/package.json`
- Create: `eve_agent/tsconfig.json`
- Create: `eve_agent/.env.example`
- Modify: `.gitignore`

**Step 1: Write the failing checks**

Run:

```bash
test -f eve_agent/package.json
test -f eve_agent/tsconfig.json
test -f eve_agent/.env.example
grep -q "eve_agent/node_modules/" .gitignore
```

Expected: at least the first command fails because `eve_agent/` does not exist yet.

**Step 2: Create `eve_agent/package.json`**

```json
{
  "name": "deepline-gtm-eve-agent",
  "private": true,
  "type": "module",
  "engines": {
    "node": "24.x"
  },
  "scripts": {
    "dev": "eve dev",
    "build": "eve build",
    "start": "eve start",
    "typecheck": "tsc --noEmit",
    "test": "tsx --test tests/**/*.test.ts",
    "eval": "eve eval",
    "smoke": "tsx scripts/smoke.ts"
  },
  "dependencies": {
    "ai": "latest",
    "eve": "latest",
    "zod": "latest"
  },
  "devDependencies": {
    "@types/node": "latest",
    "tsx": "latest",
    "typescript": "latest"
  }
}
```

**Step 3: Create `eve_agent/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "types": ["node"]
  },
  "include": ["agent/**/*.ts", "evals/**/*.ts", "scripts/**/*.ts", "tests/**/*.ts"]
}
```

**Step 4: Create `eve_agent/.env.example`**

```bash
# Deepline execution backend
DEEPLINE_API_KEY=dlp_...
# Optional override; defaults to https://code.deepline.com
# DEEPLINE_API_BASE_URL=https://code.deepline.com

# Eve model path
# Preferred on Vercel: link a Vercel project and use AI Gateway/OIDC.
# Local direct-provider fallback:
# ANTHROPIC_API_KEY=sk-ant-...
# AI_GATEWAY_API_KEY=...
# EVE_MODEL=anthropic/claude-sonnet-4.6
```

**Step 5: Update `.gitignore`**

Add:

```gitignore

# Eve / Node local artifacts
eve_agent/node_modules/
eve_agent/.eve/
eve_agent/.vercel/
eve_agent/dist/
eve_agent/*.tsbuildinfo
```

**Step 6: Run checks**

Run:

```bash
test -f eve_agent/package.json
test -f eve_agent/tsconfig.json
test -f eve_agent/.env.example
grep -q "eve_agent/node_modules/" .gitignore
```

Expected: all pass.

**Step 7: Commit**

```bash
git add .gitignore eve_agent/package.json eve_agent/tsconfig.json eve_agent/.env.example
git commit -m "feat: add eve agent project skeleton"
```

---

### Task 2: Add TypeScript Deepline v2 Client

**Files:**
- Create: `eve_agent/agent/lib/deepline.ts`
- Create: `eve_agent/tests/deepline.test.ts`

**Step 1: Write the failing test**

Create `eve_agent/tests/deepline.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import {
  DeeplineClient,
  extractTextFromSseChunk,
  streamToTextAndToolCalls,
} from "../agent/lib/deepline.js";

test("executeTool uses Deepline v2 tool route", async () => {
  const requests: Array<{ url: string; init: RequestInit }> = [];
  const fetcher = async (url: string | URL, init?: RequestInit) => {
    requests.push({ url: String(url), init: init ?? {} });
    return new Response(
      JSON.stringify({ status: "completed", toolResponse: { raw: { email: "jane@acme.com" } } }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  };

  const client = new DeeplineClient({
    apiKey: "dl_test",
    baseUrl: "https://code.deepline.com",
    fetcher,
  });

  const result = await client.executeTool("hunter_email_finder", { domain: "acme.com" });

  assert.equal(requests[0].url, "https://code.deepline.com/api/v2/integrations/hunter_email_finder/execute");
  assert.equal((requests[0].init.headers as Record<string, string>).Authorization, "Bearer dl_test");
  assert.equal(
    (requests[0].init.headers as Record<string, string>)["x-deepline-execute-response-contract"],
    "v2-tool-response",
  );
  assert.equal((result as any).toolResponse.raw.email, "jane@acme.com");
});

test("extractTextFromSseChunk parses common Deepline stream events", () => {
  const chunk = [
    'data: {"type":"text-delta","textDelta":"hello"}',
    'data: {"type":"text-delta","delta":" world"}',
    "data: [DONE]",
    "",
  ].join("\n");

  assert.equal(extractTextFromSseChunk(chunk), "hello world");
});

test("streamToTextAndToolCalls captures text and tool-call metadata", async () => {
  async function* chunks() {
    yield 'data: {"type":"tool-call","toolName":"exa_search","input":{"query":"stripe"}}\n\n';
    yield 'data: {"type":"text-delta","textDelta":"done"}\n\n';
  }

  const result = await streamToTextAndToolCalls(chunks());

  assert.equal(result.reply, "done");
  assert.deepEqual(result.toolCalls, [{ toolName: "exa_search", payloadKeys: ["query"] }]);
});
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd eve_agent
npm install
npm test
```

Expected: FAIL with module not found for `agent/lib/deepline.js`.

**Step 3: Implement `eve_agent/agent/lib/deepline.ts`**

```ts
export const DEFAULT_DEEPLINE_BASE_URL = "https://code.deepline.com";
export const V2_EXECUTE_RESPONSE_CONTRACT = "v2-tool-response";

export interface DeeplineClientOptions {
  apiKey?: string;
  baseUrl?: string;
  fetcher?: typeof fetch;
}

export interface DeeplineToolCall {
  toolName: string;
  payloadKeys: string[];
}

export interface DeeplineStreamResult {
  reply: string;
  toolCalls: DeeplineToolCall[];
}

export class DeeplineClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(options: DeeplineClientOptions = {}) {
    const apiKey = options.apiKey ?? process.env.DEEPLINE_API_KEY ?? "";
    if (!apiKey) {
      throw new Error("DEEPLINE_API_KEY is required.");
    }
    this.apiKey = apiKey;
    this.baseUrl = (
      options.baseUrl ??
      process.env.DEEPLINE_HOST_URL ??
      process.env.DEEPLINE_API_BASE_URL ??
      DEFAULT_DEEPLINE_BASE_URL
    ).replace(/\/+$/, "");
    this.fetcher = options.fetcher ?? fetch;
  }

  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      "x-deepline-execute-response-contract": V2_EXECUTE_RESPONSE_CONTRACT,
    };
  }

  async executeTool(toolId: string, payload: Record<string, unknown> = {}) {
    const response = await this.fetcher(
      `${this.baseUrl}/api/v2/integrations/${encodeURIComponent(toolId)}/execute`,
      {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ payload }),
      },
    );
    await assertOk(response, `Deepline tool ${toolId} failed`);
    return await response.json();
  }

  async *streamAgent(payload: Record<string, unknown>): AsyncGenerator<string> {
    const response = await this.fetcher(`${this.baseUrl}/api/v2/integrations/deeplineagent/stream`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });
    await assertOk(response, "Deepline native agent stream failed");
    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
  }
}

async function assertOk(response: Response, prefix: string) {
  if (response.ok) return;
  const body = await response.text().catch(() => "");
  throw new Error(`${prefix}: HTTP ${response.status} ${body.slice(0, 500)}`);
}

export function extractTextFromSseChunk(chunk: string): string {
  let text = "";
  for (const rawLine of chunk.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line.startsWith("data:")) continue;
    const data = line.slice("data:".length).trim();
    if (!data || data === "[DONE]") continue;
    let event: unknown;
    try {
      event = JSON.parse(data);
    } catch {
      continue;
    }
    if (!event || typeof event !== "object") continue;
    const obj = event as Record<string, unknown>;
    for (const key of ["text", "textDelta", "delta"]) {
      if (typeof obj[key] === "string") {
        text += obj[key];
        break;
      }
    }
    const part = obj.part;
    if (part && typeof part === "object") {
      const partObj = part as Record<string, unknown>;
      if (typeof partObj.text === "string") text += partObj.text;
      else if (typeof partObj.textDelta === "string") text += partObj.textDelta;
    }
  }
  return text;
}

export async function streamToTextAndToolCalls(chunks: AsyncIterable<string>): Promise<DeeplineStreamResult> {
  let reply = "";
  const toolCalls: DeeplineToolCall[] = [];
  for await (const chunk of chunks) {
    reply += extractTextFromSseChunk(chunk);
    toolCalls.push(...extractToolCallsFromSseChunk(chunk));
  }
  return { reply: reply.trim(), toolCalls };
}

function extractToolCallsFromSseChunk(chunk: string): DeeplineToolCall[] {
  const calls: DeeplineToolCall[] = [];
  for (const rawLine of chunk.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line.startsWith("data:")) continue;
    const data = line.slice("data:".length).trim();
    if (!data || data === "[DONE]") continue;
    let event: unknown;
    try {
      event = JSON.parse(data);
    } catch {
      continue;
    }
    if (!event || typeof event !== "object") continue;
    const obj = event as Record<string, unknown>;
    if (obj.type !== "tool-call" && obj.type !== "tool_call") continue;
    const toolName = obj.toolName ?? obj.tool_name ?? obj.name;
    if (typeof toolName !== "string" || !toolName) continue;
    const input = obj.input && typeof obj.input === "object" ? obj.input as Record<string, unknown> : {};
    calls.push({ toolName, payloadKeys: Object.keys(input) });
  }
  return calls;
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd eve_agent
npm test
npm run typecheck
```

Expected: PASS.

**Step 5: Commit**

```bash
git add eve_agent/package-lock.json eve_agent/agent/lib/deepline.ts eve_agent/tests/deepline.test.ts
git commit -m "feat: add eve deepline v2 client"
```

---

### Task 3: Port Prompt Guidance Heuristics

**Files:**
- Create: `eve_agent/agent/lib/guidance.ts`
- Create: `eve_agent/tests/guidance.test.ts`

**Step 1: Write the failing test**

Create `eve_agent/tests/guidance.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { buildGuidedPrompt } from "../agent/lib/guidance.js";

test("bulk prospect lists get native v2 list and approval guidance", () => {
  const prompt = buildGuidedPrompt("Build a CSV prospect list of 20 VP Engineering contacts.");
  assert.match(prompt, /^Bulk prospect\/list requests/);
  assert.match(prompt, /native v2 list-building workflow/);
  assert.match(prompt, /pilot\/sample first/);
  assert.match(prompt, /Production GTM agent requests must use this operating loop/);
});

test("production GTM agent requests get source verify approve writeback loop", () => {
  const prompt = buildGuidedPrompt("Build a GTM agent that researches accounts and writes back to Salesforce.");
  assert.match(prompt, /^Production GTM agent requests must use this operating loop/);
  assert.match(prompt, /Approval gate/);
  assert.match(prompt, /Write back/);
  assert.match(prompt, /Composio: tool use needs auth/);
});

test("Snowflake requests get read-only SQL guidance", () => {
  const prompt = buildGuidedPrompt("Use Snowflake to query product usage for churn risk.");
  assert.match(prompt, /^Snowflake\/warehouse query requests must use this read-only operating loop/);
  assert.match(prompt, /Use read-only SELECT queries only/);
  assert.match(prompt, /Never run INSERT/);
  assert.match(prompt, /approval before CRM writeback/);
});

test("plain one-off requests pass through unchanged", () => {
  assert.equal(
    buildGuidedPrompt("Find the LinkedIn URL for Jensen Huang at NVIDIA."),
    "Find the LinkedIn URL for Jensen Huang at NVIDIA.",
  );
});
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd eve_agent
npm test
```

Expected: FAIL with module not found for `agent/lib/guidance.js`.

**Step 3: Implement `eve_agent/agent/lib/guidance.ts`**

```ts
export const BULK_PROSPECT_LIST_INSTRUCTIONS = `Bulk prospect/list requests must use Deepline's native v2 list-building workflow.
Create an execution plan, produce or reference an auditable seed list, and run only
a pilot/sample first unless the user has explicitly approved the full run. Do not
invent prospects, companies, emails, LinkedIn URLs, or CSV rows. If a CSV/artifact
is requested, return the artifact/status details Deepline produced and the next
approval step before any full enrichment.`;

export const PRODUCTION_GTM_AGENT_INSTRUCTIONS = `Production GTM agent requests must use this operating loop:

1. Source: gather account/contact/context from named systems or web sources.
2. Verify: state what is confirmed, what is inferred, and what is missing.
3. Bound tools: use only the minimum tools needed; respect auth/scopes and do not
   spray every provider when a focused workflow or Deepline play exists.
4. Draft/recommend: produce the next action with source-backed reasoning.
5. Approval gate: ask before sending outreach, changing CRM data, enrolling in a
   sequence, creating a task, or writing back to a system of record.
6. Write back: after approval, update the chosen system and include the record ID,
   source fields, and timestamp in the response.
7. Learn: summarize the outcome signal that should improve the next run.

Bias toward the patterns from the Deepline x Exa GTM + AI talks:
- LangChain: approval loops and traceable agent reasoning.
- Exa: search should return workflow-ready context, not generic link dumps.
- Composio: tool use needs auth, scopes, and execution boundaries.
- AssemblyAI: voice/conversation agents need persistent context before action.
- Deepline: the data layer and writeback loop are usually the bottleneck.`;

export const SNOWFLAKE_QUERY_AGENT_INSTRUCTIONS = `Snowflake/warehouse query requests must use this read-only operating loop:

1. Interpret the business question and restate the metric/entity/time window.
2. Identify likely tables and fields before querying.
3. Propose the SQL before execution when the schema or metric definition is ambiguous.
4. Use read-only SELECT queries only. Never run INSERT, UPDATE, DELETE, MERGE,
   CREATE, DROP, ALTER, COPY, GRANT, or external stage operations.
5. Limit exploratory queries and avoid exporting unnecessary row-level data.
6. Explain joins, filters, and caveats in the result.
7. Ask for approval before CRM writeback, outreach, task creation, or sharing
   sensitive rows outside the system.`;

const BULK_LIST_TERMS = ["csv", "list", "prospect", "prospects", "contacts", "accounts"];
const BULK_ACTION_TERMS = ["build", "create", "find", "source", "generate"];
const BULK_COUNT_TERMS = ["5", "10", "20", "25", "50", "100", "bulk", "batch"];
const PRODUCTION_AGENT_TERMS = [
  "agent",
  "agents",
  "workflow",
  "writeback",
  "write back",
  "approval",
  "approve",
  "crm",
  "salesforce",
  "hubspot",
  "sequence",
  "outreach",
  "voice",
  "call",
  "lead magnet",
  "build kit",
];
const SNOWFLAKE_SOURCE_TERMS = ["snowflake", "warehouse", "sql", "data warehouse"];
const SNOWFLAKE_ANALYTIC_TERMS = [
  "query",
  "table",
  "tables",
  "activation",
  "product usage",
  "churn",
  "renewal",
  "pipeline",
  "account owner",
];

export function buildGuidedPrompt(message: string): string {
  if (looksLikeBulkProspectList(message)) {
    return `${BULK_PROSPECT_LIST_INSTRUCTIONS}\n\n${PRODUCTION_GTM_AGENT_INSTRUCTIONS}\n\nUser request:\n${message}`;
  }
  return withSnowflakeGuidance(withProductionGuidance(message));
}

function withProductionGuidance(message: string): string {
  if (!looksLikeProductionAgentRequest(message)) return message;
  if (message.includes("Production GTM agent requests must use this operating loop")) return message;
  return `${PRODUCTION_GTM_AGENT_INSTRUCTIONS}\n\nUser request:\n${message}`;
}

function withSnowflakeGuidance(message: string): string {
  if (!looksLikeSnowflakeQuery(message)) return message;
  if (message.includes("Snowflake/warehouse query requests must use this read-only operating loop")) return message;
  return `${SNOWFLAKE_QUERY_AGENT_INSTRUCTIONS}\n\nUser request:\n${message}`;
}

function looksLikeBulkProspectList(message: string): boolean {
  const text = message.toLowerCase();
  return hasAny(text, BULK_LIST_TERMS) && hasAny(text, BULK_ACTION_TERMS) && hasAny(text, BULK_COUNT_TERMS);
}

function looksLikeProductionAgentRequest(message: string): boolean {
  return hasAny(message.toLowerCase(), PRODUCTION_AGENT_TERMS);
}

function looksLikeSnowflakeQuery(message: string): boolean {
  const text = message.toLowerCase();
  return hasAny(text, SNOWFLAKE_SOURCE_TERMS) && hasAny(text, SNOWFLAKE_ANALYTIC_TERMS);
}

function hasAny(text: string, terms: string[]): boolean {
  return terms.some((term) => text.includes(term));
}
```

**Step 4: Run tests**

Run:

```bash
cd eve_agent
npm test
npm run typecheck
```

Expected: PASS.

**Step 5: Commit**

```bash
git add eve_agent/agent/lib/guidance.ts eve_agent/tests/guidance.test.ts
git commit -m "feat: port gtm guidance to eve"
```

---

### Task 4: Port Workflow Presets

**Files:**
- Create: `eve_agent/agent/lib/workflow-presets.ts`
- Create: `eve_agent/tests/workflow-presets.test.ts`

**Step 1: Write the failing test**

Create `eve_agent/tests/workflow-presets.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { getWorkflowPreset, listWorkflowPresets } from "../agent/lib/workflow-presets.js";

test("workflow presets expose the same core preset ids as Python broker", () => {
  const ids = new Set(listWorkflowPresets().map((preset) => preset.id));
  for (const id of [
    "inbound_lead_approval",
    "account_digest",
    "self_serve_support_agent",
    "web_context_research",
    "bounded_tool_action",
    "closed_loop_gtm_workflow",
    "snowflake_query_agent",
  ]) {
    assert.equal(ids.has(id), true, `${id} should be listed`);
  }
});

test("web_context_research includes tool bounds and output shape", () => {
  const preset = getWorkflowPreset("web_context_research");
  assert.equal(preset?.speaker_pattern, "Exa / Scott Langille");
  assert.deepEqual(preset?.suggested_tool_bounds.enabledToolIds, ["deeplineagent", "firecrawl_search", "exa_search"]);
  assert.equal(preset?.suggested_tool_bounds.maxToolCalls, 6);
  assert.ok(preset?.expected_output.includes("source-backed claims"));
});

test("unknown workflow preset returns null", () => {
  assert.equal(getWorkflowPreset("nope"), null);
});
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd eve_agent
npm test
```

Expected: FAIL with module not found.

**Step 3: Implement `eve_agent/agent/lib/workflow-presets.ts`**

Use `managed_agent/workflow_presets.py` as the source of truth and port the full `WORKFLOW_PRESETS` object to TypeScript. Preserve every preset id, `title`, `speaker_pattern`, `why`, `best_for`, `prompt`, `suggested_tool_bounds`, `expected_output`, and `human_approval_required_for`.

The module shape must be:

```ts
export interface WorkflowPreset {
  title: string;
  speaker_pattern: string;
  why: string;
  best_for: string[];
  prompt: string;
  suggested_tool_bounds: Record<string, unknown>;
  expected_output: string[];
  human_approval_required_for: string[];
}

export type WorkflowPresetWithId = WorkflowPreset & { id: string };

export const WORKFLOW_PRESETS: Record<string, WorkflowPreset> = {
  // Port every entry from managed_agent/workflow_presets.py exactly.
};

export function listWorkflowPresets(): Array<Pick<WorkflowPresetWithId, "id" | "title" | "speaker_pattern" | "best_for">> {
  return Object.entries(WORKFLOW_PRESETS).map(([id, preset]) => ({
    id,
    title: preset.title,
    speaker_pattern: preset.speaker_pattern,
    best_for: preset.best_for,
  }));
}

export function getWorkflowPreset(id: string): WorkflowPresetWithId | null {
  const preset = WORKFLOW_PRESETS[id];
  return preset ? { id, ...preset } : null;
}
```

**Step 4: Run tests**

Run:

```bash
cd eve_agent
npm test
npm run typecheck
```

Expected: PASS.

**Step 5: Commit**

```bash
git add eve_agent/agent/lib/workflow-presets.ts eve_agent/tests/workflow-presets.test.ts
git commit -m "feat: port workflow presets to eve"
```

---

### Task 5: Add Eve Agent Config, Instructions, and HTTP Channel

**Files:**
- Create: `eve_agent/agent/agent.ts`
- Create: `eve_agent/agent/instructions.md`
- Create: `eve_agent/agent/channels/eve.ts`

**Step 1: Write the failing checks**

Run:

```bash
test -f eve_agent/agent/agent.ts
test -f eve_agent/agent/instructions.md
test -f eve_agent/agent/channels/eve.ts
```

Expected: FAIL because the agent files do not exist.

**Step 2: Create `eve_agent/agent/agent.ts`**

```ts
import { defineAgent } from "eve";

export default defineAgent({
  model: process.env.EVE_MODEL ?? "anthropic/claude-sonnet-4.6",
  compaction: {
    thresholdPercent: 0.8,
  },
});
```

**Step 3: Create `eve_agent/agent/channels/eve.ts`**

```ts
import { localDev, vercelOidc } from "eve/channels/auth";
import { eveChannel } from "eve/channels/eve";

export default eveChannel({
  auth: [localDev(), vercelOidc()],
});
```

**Step 4: Create `eve_agent/agent/instructions.md`**

```md
You are the Deepline GTM Agent running in Eve.

Your job is to help authenticated business users execute go-to-market workflows through Deepline. Deepline is the execution backend for tool routing, enrichment, research, CRM actions, provider credentials, billing, and native GTM workflows.

For GTM work, call the `deepline_chat` tool with the user's request. Do not invent contacts, emails, LinkedIn URLs, company facts, CRM record IDs, campaign IDs, or provider results. If Deepline returns no data, a credential error, or a coverage gap, say that plainly and recommend the next safe step.

Standing operating loop:

1. Source: gather account, contact, conversation, CRM, warehouse, or web context from named systems or Deepline-backed sources.
2. Verify: state what is confirmed, what is inferred, and what is missing.
3. Bound tools: use the minimum tools needed. Prefer Deepline native workflows and plays over broad provider spraying.
4. Draft or recommend: produce the next action with source-backed reasoning.
5. Approval: ask before sending outreach, changing CRM data, enrolling in a sequence, creating a task, exporting sensitive data, or writing back to a system of record.
6. Write back: after approval, update the chosen system and return record IDs, changed fields, source fields, and timestamps.
7. Learn: summarize the outcome signal that should improve the next run.

Bulk prospecting and CSV/list work must use a pilot/sample first and stop for explicit approval before full enrichment.

Snowflake and warehouse workflows are read-only by default. Propose SQL before execution when the schema or metric definition is ambiguous. Never run non-SELECT operations unless a human explicitly approves an appropriate downstream workflow.

When the user asks what workflows are available, call `list_workflow_presets`. When the user asks for one preset in detail, call `get_workflow_preset`.
```

**Step 5: Run checks**

Run:

```bash
cd eve_agent
npm run typecheck
```

Expected: PASS.

**Step 6: Commit**

```bash
git add eve_agent/agent/agent.ts eve_agent/agent/instructions.md eve_agent/agent/channels/eve.ts
git commit -m "feat: add eve agent config and instructions"
```

---

### Task 6: Add Eve Tools for Deepline and Workflow Presets

**Files:**
- Create: `eve_agent/agent/tools/deepline_chat.ts`
- Create: `eve_agent/agent/tools/deepline_execute_tool.ts`
- Create: `eve_agent/agent/tools/list_workflow_presets.ts`
- Create: `eve_agent/agent/tools/get_workflow_preset.ts`
- Create: `eve_agent/tests/tool-modules.test.ts`

**Step 1: Write the failing test**

Create `eve_agent/tests/tool-modules.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

test("Eve tool modules can be imported", async () => {
  const modules = await Promise.all([
    import("../agent/tools/deepline_chat.js"),
    import("../agent/tools/deepline_execute_tool.js"),
    import("../agent/tools/list_workflow_presets.js"),
    import("../agent/tools/get_workflow_preset.js"),
  ]);
  for (const mod of modules) {
    assert.equal(typeof mod.default, "object");
  }
});
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd eve_agent
npm test
```

Expected: FAIL with missing tool modules.

**Step 3: Create `eve_agent/agent/tools/deepline_chat.ts`**

```ts
import { defineTool } from "eve/tools";
import { z } from "zod";
import { DeeplineClient, streamToTextAndToolCalls } from "../lib/deepline.js";
import { buildGuidedPrompt } from "../lib/guidance.js";

export default defineTool({
  description: "Send a GTM request to Deepline native v2 agent/chat and return the final response plus tool-call metadata.",
  inputSchema: z.object({
    message: z.string().min(1),
    messages: z.array(z.object({ role: z.string(), content: z.string() })).optional(),
    enabledToolIds: z.array(z.string()).optional(),
    maxToolCalls: z.number().int().positive().optional(),
    model: z.string().optional(),
  }),
  outputSchema: z.object({
    reply: z.string(),
    toolCalls: z.array(z.object({ toolName: z.string(), payloadKeys: z.array(z.string()) })),
  }),
  async execute(input) {
    const prompt = buildGuidedPrompt(input.message);
    const payload: Record<string, unknown> = {
      prompt,
      messages: input.messages && prompt === input.message
        ? input.messages
        : [{ role: "user", content: prompt }],
      response_mode: "stream",
    };
    if (input.enabledToolIds) payload.enabledToolIds = input.enabledToolIds;
    if (input.maxToolCalls) payload.maxToolCalls = input.maxToolCalls;
    if (input.model) payload.model = input.model;

    return await streamToTextAndToolCalls(new DeeplineClient().streamAgent(payload));
  },
  toModelOutput(output) {
    return {
      type: "text",
      value: output.reply || "Deepline returned no final text. Check tool-call metadata or retry with more context.",
    };
  },
});
```

**Step 4: Create `eve_agent/agent/tools/deepline_execute_tool.ts`**

```ts
import { defineTool } from "eve/tools";
import { z } from "zod";
import { DeeplineClient } from "../lib/deepline.js";

export default defineTool({
  description: "Execute one specific Deepline v2 tool by tool id and payload. Use only for bounded direct operations, not loops.",
  inputSchema: z.object({
    toolId: z.string().min(1),
    payload: z.record(z.string(), z.unknown()).default({}),
  }),
  async execute({ toolId, payload }) {
    return await new DeeplineClient().executeTool(toolId, payload);
  },
});
```

**Step 5: Create workflow preset tools**

`eve_agent/agent/tools/list_workflow_presets.ts`:

```ts
import { defineTool } from "eve/tools";
import { z } from "zod";
import { listWorkflowPresets } from "../lib/workflow-presets.js";

export default defineTool({
  description: "List Deepline GTM starter workflow presets with id, title, speaker pattern, and best-fit use cases.",
  inputSchema: z.object({}),
  async execute() {
    return { presets: listWorkflowPresets() };
  },
});
```

`eve_agent/agent/tools/get_workflow_preset.ts`:

```ts
import { defineTool } from "eve/tools";
import { z } from "zod";
import { getWorkflowPreset } from "../lib/workflow-presets.js";

export default defineTool({
  description: "Get one Deepline GTM workflow preset by id, including prompt, tool bounds, expected output, and approval requirements.",
  inputSchema: z.object({ presetId: z.string().min(1) }),
  async execute({ presetId }) {
    const preset = getWorkflowPreset(presetId);
    if (!preset) return { error: "Unknown workflow preset", presetId };
    return preset;
  },
});
```

**Step 6: Run tests**

Run:

```bash
cd eve_agent
npm test
npm run typecheck
```

Expected: PASS.

**Step 7: Commit**

```bash
git add eve_agent/agent/tools eve_agent/tests/tool-modules.test.ts
git commit -m "feat: add eve deepline tools"
```

---

### Task 7: Add Eve Evals for Smoke and Parity

**Files:**
- Create: `eve_agent/evals/evals.config.ts`
- Create: `eve_agent/evals/smoke.eval.ts`
- Create: `eve_agent/evals/workflow-presets.eval.ts`
- Create: `eve_agent/evals/parity/enrichment.eval.ts`
- Create: `eve_agent/evals/parity/research.eval.ts`
- Create: `eve_agent/evals/parity/approval-guidance.eval.ts`

**Step 1: Write the failing checks**

Run:

```bash
test -f eve_agent/evals/evals.config.ts
test -f eve_agent/evals/smoke.eval.ts
test -f eve_agent/evals/parity/enrichment.eval.ts
```

Expected: FAIL because eval files do not exist.

**Step 2: Create eval config**

`eve_agent/evals/evals.config.ts`:

```ts
import { defineEvalConfig } from "eve/evals";

export default defineEvalConfig({
  timeoutMs: 180_000,
  maxConcurrency: 1,
});
```

**Step 3: Create smoke eval**

`eve_agent/evals/smoke.eval.ts`:

```ts
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Eve app boots and can answer a simple non-tool greeting.",
  tags: ["smoke"],
  async test(t) {
    await t.send("Say ok in one word.");
    t.completed();
    t.check(t.reply.toLowerCase(), includes("ok"));
  },
});
```

**Step 4: Create workflow preset eval**

`eve_agent/evals/workflow-presets.eval.ts`:

```ts
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Workflow presets are discoverable from the Eve agent.",
  tags: ["workflow-presets", "parity"],
  async test(t) {
    await t.send("List the available Deepline GTM workflow presets.");
    t.completed();
    t.calledTool("list_workflow_presets");
    t.check(t.reply, includes("web_context_research"));
    t.check(t.reply, includes("snowflake_query_agent"));
  },
});
```

**Step 5: Create parity evals**

`eve_agent/evals/parity/enrichment.eval.ts`:

```ts
import { defineEval } from "eve/evals";
import { includesAny } from "eve/evals/expect";

export default defineEval({
  description: "Contact enrichment routes through Deepline.",
  tags: ["parity", "enrichment"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("Find the work email for Satya Nadella at microsoft.com");
    t.completed();
    t.calledTool("deepline_chat");
    t.check(t.reply, includesAny(["email", "microsoft", "credential", "could not", "@"]));
  },
});
```

`eve_agent/evals/parity/research.eval.ts`:

```ts
import { defineEval } from "eve/evals";
import { includesAny } from "eve/evals/expect";

export default defineEval({
  description: "Account research routes through Deepline and returns GTM-relevant output.",
  tags: ["parity", "research"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("Research stripe.com and summarize GTM-relevant signals.");
    t.completed();
    t.calledTool("deepline_chat");
    t.check(t.reply.toLowerCase(), includesAny(["stripe", "source", "research", "signals", "could not"]));
  },
});
```

`eve_agent/evals/parity/approval-guidance.eval.ts`:

```ts
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Risky workflows preserve pilot, approval, and writeback guidance.",
  tags: ["parity", "approval"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("Build a CSV prospect list of 20 VP Sales contacts and write approved updates back to Salesforce.");
    t.completed();
    t.calledTool("deepline_chat");
    t.check(t.reply.toLowerCase(), includes("approval"));
    t.check(t.reply.toLowerCase(), includes("pilot"));
  },
});
```

If `includesAny` is not exported by the installed Eve version, replace those assertions with multiple `includes(...).soft()` checks and one LLM judge gate.

**Step 6: Run typecheck**

Run:

```bash
cd eve_agent
npm run typecheck
```

Expected: PASS.

**Step 7: Run local smoke eval**

Run:

```bash
cd eve_agent
npm run eval -- smoke
```

Expected: PASS if a model credential is configured. If credentials are missing, Eve should report the missing model credential clearly.

**Step 8: Commit**

```bash
git add eve_agent/evals
git commit -m "test: add eve smoke and parity evals"
```

---

### Task 8: Add Deployment Smoke Script

**Files:**
- Create: `eve_agent/scripts/smoke.ts`

**Step 1: Write the failing check**

Run:

```bash
cd eve_agent
npm run smoke -- --host http://127.0.0.1:3000
```

Expected: FAIL because `scripts/smoke.ts` does not exist.

**Step 2: Create `eve_agent/scripts/smoke.ts`**

```ts
const host = getArg("--host") ?? process.env.EVE_HOST ?? "http://127.0.0.1:3000";
const message = getArg("--message") ?? "Say ok in one word.";

async function main() {
  const health = await fetch(`${host.replace(/\/+$/, "")}/eve/v1/health`);
  if (!health.ok) throw new Error(`Health failed: HTTP ${health.status} ${await health.text()}`);

  const session = await fetch(`${host.replace(/\/+$/, "")}/eve/v1/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!session.ok) throw new Error(`Session create failed: HTTP ${session.status} ${await session.text()}`);
  const body = await session.json() as { sessionId?: string; continuationToken?: string };
  if (!body.sessionId) throw new Error(`No sessionId in response: ${JSON.stringify(body)}`);

  const stream = await fetch(`${host.replace(/\/+$/, "")}/eve/v1/session/${body.sessionId}/stream`);
  if (!stream.ok) throw new Error(`Stream failed: HTTP ${stream.status} ${await stream.text()}`);
  if (!stream.body) throw new Error("Stream response had no body.");

  const reader = stream.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  let sawCompletion = false;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
    if (text.includes('"type":"session.completed"') || text.includes('"type":"session.waiting"')) {
      sawCompletion = true;
      break;
    }
  }
  if (!sawCompletion) throw new Error(`No completion/waiting event seen. Stream so far:\n${text.slice(0, 2000)}`);
  console.log(JSON.stringify({ ok: true, host, sessionId: body.sessionId }));
}

function getArg(name: string): string | undefined {
  const idx = process.argv.indexOf(name);
  return idx >= 0 ? process.argv[idx + 1] : undefined;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

**Step 3: Run typecheck**

Run:

```bash
cd eve_agent
npm run typecheck
```

Expected: PASS.

**Step 4: Commit**

```bash
git add eve_agent/scripts/smoke.ts
git commit -m "test: add eve deployment smoke script"
```

---

### Task 9: Add Eve Documentation and Faster Deployment Path

**Files:**
- Create: `eve_agent/README.md`
- Modify: `README.md`
- Modify: `SETUP.md`

**Step 1: Write the failing doc checks**

Run:

```bash
test -f eve_agent/README.md
grep -q "Eve reference implementation" README.md
grep -q "Eve on Vercel" SETUP.md
```

Expected: FAIL because docs are not added yet.

**Step 2: Create `eve_agent/README.md`**

```md
# Deepline GTM Eve Agent

This is the additive Eve reference implementation for `deepline-gtm-agent`.

The existing Python/FastAPI broker remains the default runtime. This app proves the same Deepline GTM behavior on Eve: filesystem-first agent files, durable sessions, Eve evals, and faster Vercel deployment.

## Requirements

- Node 24
- npm
- `DEEPLINE_API_KEY`
- A model credential for Eve: Vercel AI Gateway/OIDC, `AI_GATEWAY_API_KEY`, or a direct provider key such as `ANTHROPIC_API_KEY`

## Local Setup

```bash
cd eve_agent
npm install
cp .env.example .env.local
# fill DEEPLINE_API_KEY and a model credential
npm run dev
```

Create a session:

```bash
curl -X POST http://127.0.0.1:3000/eve/v1/session \
  -H "content-type: application/json" \
  -d '{"message":"Research stripe.com and summarize GTM-relevant signals."}'
```

Stream it:

```bash
curl -N http://127.0.0.1:3000/eve/v1/session/<sessionId>/stream
```

## Verify

```bash
npm test
npm run typecheck
npm run build
npm run eval -- smoke
```

With live Deepline credentials:

```bash
npm run eval -- parity
```

## Deploy Faster on Vercel

```bash
cd eve_agent
npm install
npm run build
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 vercel deploy
```

Set these Vercel environment variables:

- `DEEPLINE_API_KEY`
- model credential path: Vercel AI Gateway/OIDC, `AI_GATEWAY_API_KEY`, or direct provider key
- optional `EVE_MODEL`

Smoke test the deployment:

```bash
npm run smoke -- --host https://<your-eve-app>.vercel.app
```
```

**Step 3: Update root `README.md`**

Add a short section after the current architecture section:

```md
## Eve reference implementation

This repo also contains an additive Eve implementation in `eve_agent/`. It is not the default runtime yet. Use it to validate Deepline GTM workflows on Eve's durable session model and faster Vercel deployment path.

Start with:

```bash
cd eve_agent
npm install
npm run dev
```

The existing Python/FastAPI broker remains the stable default until Eve parity evals pass end to end.
```

**Step 4: Update `SETUP.md`**

Add a section:

```md
## Eve on Vercel

The additive Eve implementation lives in `eve_agent/` and deploys directly to Vercel.

```bash
cd eve_agent
npm install
npm run build
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 vercel deploy
```

Required variables:

| Variable | Required | Description |
|---|---|---|
| `DEEPLINE_API_KEY` | Yes | Deepline v2 API key from code.deepline.com |
| `AI_GATEWAY_API_KEY` or provider key | Local/dev | Model credential unless using Vercel OIDC |
| `EVE_MODEL` | Optional | Defaults to `anthropic/claude-sonnet-4.6` |

Verify:

```bash
cd eve_agent
npm run smoke -- --host https://<your-eve-app>.vercel.app
npm run eval -- --url https://<your-eve-app>.vercel.app smoke
```
```

**Step 5: Run doc checks**

Run:

```bash
test -f eve_agent/README.md
grep -q "Eve reference implementation" README.md
grep -q "Eve on Vercel" SETUP.md
```

Expected: PASS.

**Step 6: Commit**

```bash
git add README.md SETUP.md eve_agent/README.md
git commit -m "docs: document eve reference implementation"
```

---

### Task 10: Run Full Local Parity Verification

**Files:**
- No file edits unless a verification failure reveals a bug in files from previous tasks.

**Step 1: Run Python tests**

Run:

```bash
pytest tests/test_v2_client.py tests/test_managed_v2_broker.py -v
```

Expected: PASS. If unrelated pre-existing local changes cause failures, inspect them and avoid reverting user-owned edits.

**Step 2: Run Eve unit and type checks**

Run:

```bash
cd eve_agent
npm test
npm run typecheck
npm run build
```

Expected: PASS.

**Step 3: Run Eve local dev smoke**

Start:

```bash
cd eve_agent
npm run dev
```

In another terminal:

```bash
cd eve_agent
npm run smoke -- --host http://127.0.0.1:3000
```

Expected: smoke script prints `{"ok":true,...}`.

**Step 4: Run Eve evals**

Run:

```bash
cd eve_agent
npm run eval -- smoke
npm run eval -- workflow-presets
```

Expected: PASS.

If `DEEPLINE_API_KEY` and model credentials are available, run:

```bash
cd eve_agent
npm run eval -- parity
```

Expected: PASS or actionable Deepline credential/data-coverage messages.

**Step 5: Commit any verification fixes**

Only if files changed:

```bash
git add <changed-files>
git commit -m "fix: complete eve parity verification"
```

---

### Task 11: Run Vercel Deployment Verification

**Files:**
- No file edits unless deployment reveals missing docs or config.

**Step 1: Build locally**

Run:

```bash
cd eve_agent
npm run build
```

Expected: PASS and `.eve/` artifacts generated locally.

**Step 2: Deploy preview**

Run:

```bash
cd eve_agent
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 vercel deploy
```

Expected: Vercel returns a preview URL.

**Step 3: Smoke test preview**

Run:

```bash
cd eve_agent
npm run smoke -- --host https://<preview-url>
```

Expected: PASS.

**Step 4: Run smoke eval against preview**

Run:

```bash
cd eve_agent
npm run eval -- --url https://<preview-url> smoke
```

Expected: PASS.

**Step 5: Document deployment result**

If needed, append deployment caveats to `eve_agent/README.md`, then commit:

```bash
git add eve_agent/README.md
git commit -m "docs: record eve deployment verification"
```

---

### Task 12: Defer Slack Until HTTP Parity Is Stable

**Files:**
- Create: `docs/plans/2026-06-17-eve-slack-followup.md`

**Step 1: Create follow-up note**

```md
# Eve Slack Follow-Up

Slack is intentionally deferred until the Eve HTTP implementation passes parity.

Next steps:

1. Add `@vercel/connect`.
2. Run `eve channels add slack`.
3. Configure Vercel Connect Slack client and trigger path `/eve/v1/slack`.
4. Port thread-context behavior from `managed_agent/server.py`.
5. Add Slack-specific eval/manual smoke checklist.
6. Verify HITL buttons and private authorization prompts.
```

**Step 2: Commit**

```bash
git add docs/plans/2026-06-17-eve-slack-followup.md
git commit -m "docs: defer eve slack follow-up"
```

---

## Final Verification Checklist

Run before declaring the Eve port complete:

```bash
pytest tests/test_v2_client.py tests/test_managed_v2_broker.py -v
cd eve_agent
npm test
npm run typecheck
npm run build
npm run eval -- smoke
npm run eval -- workflow-presets
npm run smoke -- --host http://127.0.0.1:3000
```

With live credentials and a deployed preview:

```bash
cd eve_agent
npm run eval -- parity
npm run smoke -- --host https://<preview-url>
npm run eval -- --url https://<preview-url> smoke
```

The existing Python broker remains the default until all final verification checks pass repeatedly.

