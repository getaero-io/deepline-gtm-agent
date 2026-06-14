# GTM Agent Field Guide

5 strong GTM + AI teams shared what they learned. Jai also talked. Somehow we survived.

This is the Notion-ready version of the build kit: the field notes, implementation patterns, prompts, and repo mapping from the Deepline x Exa GTM + AI talks.

Use it as:

- a lead magnet
- an internal enablement doc
- a repo companion
- a checklist before anyone ships a GTM agent with 80 tools and a prayer

## The Short Version

The useful GTM agent pattern was not "AI writes better emails."

It was:

```text
source -> verify -> bound tools -> draft/recommend -> approve -> write back -> learn
```

Every good example mapped back to that loop.

The model matters. Obviously.

But the model is not where most GTM agents break.

They break when the context is stale, the tools are overexposed, the sources are unclear, the approval step is missing, or the writeback path is an afterthought.

Very fun. Very glamorous. Basically the Monaco GP of CRM hygiene.

## What We Learned From Each Team

## 1. Vishnu Suresh / LangChain

### The lesson

Approval loops are not a safety feature bolted on at the end.

They are the product.

The useful LangChain GTM agent pattern is:

- inspect the account before acting
- look for reasons not to act
- draft the recommended action
- show the reasoning
- ask a human before the risky step
- trace what happened after the human edits or approves

The interesting part is not that the agent can write a message.

Everyone can write a message now. My toaster is probably one LangGraph tutorial away from writing a three-step outbound sequence.

The interesting part is whether the system knows when not to send.

### What to copy

Build the agent around checkpoints:

| Step | What The Agent Does | Human Role |
|---|---|---|
| Research | Pulls account/contact context | Spot missing context |
| Reason | Explains why the action is or is not appropriate | Challenge the logic |
| Draft | Produces the proposed output | Edit the actual customer-facing thing |
| Approve | Waits before side effects | Decide whether to send/write/enroll |
| Learn | Logs edits and outcomes | Improve the next run |

### What to avoid

Do not build:

```text
find lead -> generate email -> send email
```

That is not a GTM agent. That is a liability with a subject line.

### Repo mapping

In this repo:

- `managed_agent/server.py` injects the production operating loop for agent/workflow requests.
- `tests/test_managed_v2_broker.py` checks that approval/writeback guidance is included.
- `docs/gtm-agent-build-kit.md` includes starter prompts that force approval before CRM or outreach actions.
- `workflow-presets/snowflake_query_agent` covers the BI-in-chat pattern: read-only warehouse questions, proposed SQL, source tables, and approval before downstream action.

### Prompt to steal

```text
Research this account and propose the next GTM action.

Before acting:
1. show the source-backed account context
2. list reasons not to act
3. draft the recommended action
4. ask for approval before any CRM update, sequence enrollment, or customer-facing message
5. after approval, return the writeback fields and outcome signal to learn from
```

## 2. Scott Langille / Exa

### The lesson

Search is not a list of links anymore.

For GTM agents, search has to become workflow-ready context.

Bad output:

```text
Here are 10 results about the company.
```

Useful output:

```text
The company is hiring RevOps, recently launched an enterprise product, and uses Salesforce.
Sources: ...
GTM implication: route this account to a Salesforce-data-quality angle.
Confidence: medium. Missing: current CRM owner.
```

The agent does not need more tabs.

The agent needs claims it can safely use.

### What to copy

Make search return structured evidence:

| Field | Why It Matters |
|---|---|
| Source URL | Lets the human audit the claim |
| Extracted claim | Prevents vague research summaries |
| Freshness | Avoids stale personalization |
| Relevance | Maps research to a GTM action |
| Confidence | Separates fact from inference |
| Next action | Turns research into workflow |

### What to avoid

Do not let the agent summarize the internet and call it "account intelligence."

If a rep still has to open the links, inspect the site, and decide what matters, the agent did not finish the job.

### Repo mapping

In this repo:

- The REST broker supports `enabledToolIds` and `maxToolCalls`.
- `docs/gtm-agent-build-kit.md` includes bounded-tool research examples.
- `deepline_gtm_agent/tools.py` already exposes Exa/web research paths for the legacy local path.

### Prompt to steal

```text
Research this account using only web/company research tools.

Return exactly:
- 5 source-backed claims
- source URL for each claim
- why each claim matters for GTM
- confidence level
- missing context
- recommended next workflow

Do not enrich contacts.
Do not create CRM records.
Do not enroll anyone in outreach.
```

## 3. Sujay Choubey / Composio

### The lesson

More tools usually make the agent worse.

The hard part is not giving an agent access to every action in the universe.

The hard part is deciding which tools it should be allowed to use, under which auth scope, with which approval boundary, and what happens when the tool result is weird.

Tiny detail. Happens to matter.

### What to copy

Treat tool access like product surface area:

| Question | Why It Matters |
|---|---|
| What tool is available? | Tool discovery |
| Who authorized it? | Auth boundary |
| What can it touch? | Scope boundary |
| What side effect can it create? | Risk boundary |
| What needs approval? | Human control |
| What gets logged? | Debugging and learning |

### What to avoid

Do not expose 80 tools and hope the model becomes wise.

That is how you get inconsistent tool usage, hidden cost, weird retries, and an agent that technically "completed" the task while doing the wrong thing.

The dropdown was not the problem. The blast radius was.

### Repo mapping

In this repo:

- `enabledToolIds` lets callers bound tools per request.
- `maxToolCalls` limits runaway tool use.
- The production prompt tells the agent to prefer focused workflows/Deepline plays over provider spraying.
- The build-kit examples include a tool-bounded research workflow.

### Prompt to steal

```text
Use only the tools needed for this workflow.

Before tool use:
- state which tool you plan to use
- why it is needed
- whether it creates a side effect
- whether approval is required

After tool use:
- return the tool result
- return the source/cost/coverage signal
- state the next safe step
```

## 4. Matt Lawler / AssemblyAI

### The lesson

Voice agents are not useful because they are voice.

They are useful when voice becomes context the workflow can act on.

A call transcript is not the output.

The output is:

- buyer intent
- objections
- promised follow-ups
- CRM field diffs
- tasks to create
- account context to carry forward
- draft response
- approval before writeback

### What to copy

Turn conversation into structured workflow state:

| Conversation Signal | Workflow Output |
|---|---|
| Buyer asked for pricing | Create pricing follow-up draft |
| Objection surfaced | Add objection to CRM notes |
| Champion mentioned another stakeholder | Create contact research task |
| Timeline changed | Update close plan after approval |
| Next step promised | Create task after approval |

### What to avoid

Do not ship another "AI call summary" that produces polite paragraphs nobody reads.

If the rep still has to translate the summary into CRM updates, tasks, and next steps, the agent mostly made nicer homework.

### Repo mapping

In this repo:

- The production loop explicitly covers conversation context before action.
- The examples include a call follow-up agent prompt.
- The approval/writeback guidance applies before any task or CRM update.

### Prompt to steal

```text
Turn this transcript into a GTM follow-up workflow.

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

## 5. Deepline / Jai

### The lesson

The model is usually not the bottleneck.

The data layer is.

Annoying, because the model is the fun part and the data layer is where optimism goes to file a support ticket.

The real GTM agent work is deciding:

- which source wins when systems disagree
- whether the data is fresh enough
- which provider to try first
- when to stop spending credits
- what needs human approval
- what should write back to Salesforce/HubSpot/Attio
- what the next run should learn from this one

### What to copy

Use Deepline as the GTM execution layer:

| Need | Deepline Role |
|---|---|
| Provider routing | Pick the right enrichment/research path |
| Cost control | Avoid provider spraying |
| Tool catalog | Give agents GTM-native actions |
| CRM writeback | Push approved changes to systems of record |
| Session state | Track what ran, what missed, and what changed |
| Plays | Reuse workflows instead of rebuilding loops |

### What to avoid

Do not ask Claude Code, Cursor, or any agent framework to become your GTM data platform.

They can write the workflow.

They still need somewhere reliable to get the data, use the tools, and push the result.

### Repo mapping

In this repo:

- `managed_agent/server.py` brokers REST, Slack, and web chat into Deepline native v2 chat.
- `deepline_gtm_agent/v2_client.py` keeps the v2 API contract small and explicit.
- `README.md` now positions the repo as the build kit.
- `docs/gtm-agent-build-kit.md` provides the first set of prompts.
- This file is the longer Notion-ready field guide.

### Prompt to steal

```text
Build this GTM workflow using Deepline as the execution layer.

Requirements:
- source data from named systems/providers
- verify what is confirmed vs. inferred
- avoid broad provider spraying
- run a pilot/sample before full list work
- ask before CRM writeback or outreach enrollment
- return provider outcomes, missing fields, and next-run learning
```

## The Pattern To Build Into Every GTM Agent

## 1. Source

Pull context from the right places:

- CRM
- enrichment providers
- website
- job posts
- news
- transcript/call system
- previous interactions
- product usage
- Snowflake or warehouse tables

Output should name the source.

## 2. Verify

Separate facts from guesses:

- confirmed
- inferred
- stale
- missing
- conflicting

This is where a lot of GTM agents quietly fail.

They sound confident because the model is fluent. Not because the data is good.

## 3. Bound Tools

Limit the agent:

- specific tools
- max tool calls
- scoped auth
- read-only mode when possible
- side-effect tools behind approval

In this repo, use `enabledToolIds` and `maxToolCalls`.

## 4. Draft Or Recommend

The agent should explain the recommended action.

Not with a 900-word consultant memo.

Just enough to answer:

- why this account?
- why this person?
- why this message?
- why now?
- what are we missing?

## 5. Approve

Ask before:

- sending outreach
- enrolling in a sequence
- creating CRM records
- changing CRM fields
- creating tasks
- assigning owner
- spending meaningfully more credits

## 6. Write Back

After approval, return:

- system updated
- record ID
- fields changed
- source fields used
- timestamp
- link to the record if available

## 7. Learn

Capture what should improve the next run:

- human edited the opener
- email bounced
- prospect replied
- enrichment missed
- source was stale
- CRM field was wrong
- tool call was unnecessary

This is the part most demos skip.

Conveniently, it is also the part that makes the system useful after week one.

## Implementation Checklist

Before calling something a GTM agent, answer these:

- [ ] What sources does it trust?
- [ ] What happens when sources disagree?
- [ ] Which tools can it use?
- [ ] Which tools create side effects?
- [ ] Where is human approval required?
- [ ] What is the writeback target?
- [ ] What gets logged?
- [ ] What outcome teaches the next run?
- [ ] How do you stop provider/cost spraying?
- [ ] Can a rep understand why it made the recommendation?

## Repo Changes This Guide Maps To

| File | Why It Exists |
|---|---|
| `README.md` | Positions the repo as the GTM Agent Build Kit |
| `docs/gtm-agent-build-kit.md` | Short practical guide and prompt pack |
| `docs/notion-gtm-agent-field-guide.md` | Long Notion-ready guide |
| `examples.md` | Copy-paste workflows |
| `examples/requests/snowflake_query_agent.json` | Safe warehouse-backed GTM question template |
| `managed_agent/server.py` | Injects production GTM loop into relevant requests |
| `tests/test_managed_v2_broker.py` | Prevents losing approval/writeback guidance |
| `deepline_gtm_agent/prompts.py` | Mirrors the loop for the legacy Deep Agents path |

## CTA Copy For LinkedIn

```text
5 of the best GTM + AI teams shared what they learned Tuesday.

And then I also talked. Sorry in advance.

We packaged the useful parts into a GTM Agent Build Kit:
- field guide
- repo
- prompts
- workflow patterns
- production notes from LangChain, Exa, Composio, AssemblyAI, and Deepline

The useful pattern was not "AI writes better emails."

It was:
source -> verify -> bound tools -> draft -> approve -> write back -> learn

Comment AGENTS and I'll send it over.
```
