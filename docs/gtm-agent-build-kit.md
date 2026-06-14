# GTM Agent Build Kit

This repo is the practical version of the Deepline x Exa GTM + AI talks.

For the long Notion-ready field guide with speaker-by-speaker learnings, see
[`docs/notion-gtm-agent-field-guide.md`](notion-gtm-agent-field-guide.md).
For the transcript-to-usability changelog, see
[`docs/transcript-learnings-usability.md`](transcript-learnings-usability.md).

The point is not "AI writes better emails." The useful pattern is:

1. Source the context.
2. Verify what is true.
3. Bound the tools.
4. Draft or recommend the next action.
5. Ask for approval before risk.
6. Write back to the system of record.
7. Learn from the outcome.

That loop showed up across all five talks.

## What The Teams Taught

### LangChain: approval loops ship

The LangChain pattern is not "let an agent blast prospects." It is:

- inspect the account
- look for reasons not to act
- explain the proposed action
- ask a human before doing something dumb
- trace what happened so the next run improves

In this repo, that means agent and bulk-workflow requests are wrapped with the production operating loop in `managed_agent/server.py`.

### Exa: search must become workflow context

Search is not useful when it returns ten blue links and makes the rep do the work.

For GTM agents, search output should become structured context:

- source URL
- extracted claim
- timestamp or freshness hint
- relevance to the account/contact
- confidence level
- how it changes the next action

Use the prompt patterns below to force the agent to return workflow-ready context instead of generic research summaries.

### Composio: tool use needs boundaries

More tools usually make the agent worse.

The useful version is scoped:

- only expose the tools required for the workflow
- respect auth and scopes
- prefer a Deepline play or native workflow over spraying providers
- ask before any external side effect
- return the tool used, result, cost/coverage signal, and next step

This repo supports `enabledToolIds` and `maxToolCalls` in the REST payload so the caller can bound tool access per workflow.

### AssemblyAI: conversation context matters

Voice and call agents are only useful when they carry context across the workflow.

For GTM, that means:

- call summary
- speaker intent
- objections
- next steps
- account state
- CRM fields to update
- human approval before writeback

The agent should not turn a transcript into generic notes. It should produce a proposed CRM/task/update diff and wait for approval.

### Deepline: the data/writeback layer is the bottleneck

The model is usually not the hard part.

The hard part is deciding:

- which source wins when systems disagree
- which fields are fresh enough to trust
- which provider to use first
- what to do when enrichment misses
- what can be written back safely
- what should be learned from the result

That is what Deepline should own for GTM agents.

## Starter Prompts

### Account Research Agent

```text
Build an account research workflow for stripe.com.

Use the production GTM agent loop:
1. source context from web/company data
2. verify claims and show sources
3. return only workflow-ready signals
4. draft the next best GTM action
5. ask before writing anything to CRM

Output:
- account summary
- 5 source-backed signals
- what changed since the last known CRM state
- recommended next action
- approval question before writeback
```

### Lead Magnet Agent

```text
Build a GTM lead-magnet agent for a B2B SaaS company.

Input:
- target account domain
- target persona
- offer or event topic

The agent should:
- research the account and persona
- find source-backed pain/context
- draft a personalized lead magnet angle
- create a short LinkedIn DM/email opener
- ask for approval before CRM writeback or outreach enrollment
- return sources, confidence, and missing fields
```

### Call Follow-Up Agent

```text
Turn this call transcript into a GTM follow-up workflow.

Do not write generic notes.

Return:
- buyer intent
- objections
- promised follow-ups
- CRM field diffs
- recommended next step
- draft follow-up
- approval question before creating tasks or updating CRM
```

### Tool-Bounded Research Agent

```text
Research this account using only web/company research tools.

Do not enrich contacts.
Do not create CRM records.
Do not enroll anyone in outreach.

Return source-backed signals and the next suggested workflow.
```

Use this with:

```json
{
  "message": "Research linear.app and recommend the next GTM action.",
  "enabledToolIds": ["deeplineagent", "firecrawl_search", "exa_search"],
  "maxToolCalls": 6
}
```

## API Examples

### Pick a starter workflow

```bash
curl http://localhost:8000/workflow-presets
curl http://localhost:8000/workflow-presets/web_context_research
```

Use these when you do not know which prompt to start from. The presets include:

- prompt
- suggested tool bounds
- expected output
- approval requirements

### Production agent request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Build a GTM agent that researches accounts, drafts outreach, asks for approval, and writes approved updates back to Salesforce."
  }'
```

The broker will prepend the production GTM agent operating loop automatically.

### Bounded tools

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Research stripe.com and return source-backed GTM signals only.",
    "enabledToolIds": ["deeplineagent", "firecrawl_search", "exa_search"],
    "maxToolCalls": 6
  }'
```

### Bulk list with approval

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Build a CSV prospect list of 20 VP Sales contacts at fintech companies."
  }'
```

The broker will require native v2 list-building, pilot/sample first, and explicit approval before full enrichment.

## What Good Output Looks Like

Good:

```text
Recommendation: send a founder-led invite to the RevOps leader.

Why:
- confirmed the company is hiring RevOps roles
- confirmed Salesforce is in the stack
- found a recent launch that maps to data-quality pain

Missing:
- no verified mobile number
- email is catch-all, not safe for sequence yet

Approve before writeback:
Should I create the HubSpot task and attach these source fields?
```

Bad:

```text
Here are 10 exciting personalization ideas.
```

That is not an agent. That is a content blender with API access.
