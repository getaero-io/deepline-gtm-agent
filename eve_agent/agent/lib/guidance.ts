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
