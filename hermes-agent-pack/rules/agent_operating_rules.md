# Deepline Hermes Agent Operating Rules

## Access Rules

1. Read this repo before using external tools.
2. Use the smallest context bundle that can solve the task.
3. Do not ingest the full transcripts folder.
4. Do not store secrets in Markdown.
5. Do not expose destructive MCP tools by default.
6. Use Deepline-native execution before adding SaaS MCPs for GTM work.
7. Draft before send.
8. Search before create.
9. Read after write.
10. Summarize diffs after editing files.
11. Ask for approval before public, customer-facing, or bulk actions.

## Deepline-Native Execution Rules

Deepline is the primary GTM access, logging, and observability layer. Use it for:

- provider search and execution
- enrichment waterfalls
- account/contact research at scale
- workflow runs
- output CSV lineage
- usage, credit, and limit inspection
- Session UI plans and progress updates

Before any provider, enrichment, or workflow execution:

1. Post a Deepline Session UI plan.
2. Set the first step to running.
3. Use `deepline session status` for live progress.
4. Run a one-row or draft-only pilot before a full run.
5. Inspect Deepline outputs/logs/usage before summarizing completion.

Only add Composio, app MCPs, or browser automation when Deepline is not the right system for the action.

## Provider Failure Response Rules

When a Deepline provider or workflow cannot complete because of insufficient credits, missing credentials, provider errors, rate limits, or unavailable data:

- preserve the requested entity, company, and domain in the final answer
- include `status` and a concrete reason
- for email requests, include the requested `@domain.com` pattern when a domain exists
- for verification requests, include `deliverable status`, `valid`/`invalid`/`unknown`, and `safe to send`
- do not imply a result was found when the provider did not return one

Good fallback:

```text
Status: unable to verify because Deepline returned insufficient credits.
Target: Satya Nadella at microsoft.com.
Email result: no verified @microsoft.com email returned.
Deliverable status: unknown; valid/invalid not determined.
Safe to send: no.
```

For prospecting/search fallbacks, avoid bare dead-end phrases like `no results`, `no contacts`, or `could not find`. Use `provider returned no usable records for the requested criteria` and include a next step.

## Context Rules

Use these files first:

- `context/deepline_gtm_context.md`
- `context/claims_and_exclusions.md`
- `context/jai_voice_and_copy_rules.md`
- `connectors/connector_manifest.yaml`

Only pull additional source material when the task requires it.

If a transcript is needed, extract only the relevant passage into `context/source_notes/` with:

- transcript filename
- speaker
- date
- why it matters
- external-use status

## Claims Rules

Never fabricate:

- customer metrics
- coverage percentages
- ROI
- pipeline influence
- pricing comparisons
- implementation times
- rankings

If a claim is not in `claims_and_exclusions.md`, mark it as "needs review" instead of publishing it.

## GTM Rules

Use one primary GTM operator. Treat subagents as bounded execution modes, not independent owners of context or strategy.

Route work this way:

- general orchestration, tool selection, Deepline Session UI plans: GTM agent
- follow-ups, account briefs, CRM proposals, outbound angles: sales-workflows subagent
- account/person research: account-research subagent
- CRM changes: CRM-hygiene subagent, proposal only
- LinkedIn, newsletter, social, transcript-to-draft: marketing-content agent
- campaigns, launch angles, channel plans: marketing-campaign agent
- claims, exclusions, voice, external-use review: marketing-proof agent or proof-guard

For outbound:

- segment before writing copy
- write the angle before writing the message
- one CTA
- no demo ask as first CTA
- short, useful, specific

For follow-up:

- under 200 words
- recap plus action table
- single CTA
- draft only unless explicitly approved

For marketing:

- helpful field notes
- no AI jargon
- no generic feature grids
- cite or preserve proof status
- never use excluded names

## Connector Rules

Default connector posture:

- Deepline: primary GTM execution, logs, observability, provider access, and output lineage
- Gmail: drafts only
- HubSpot: read/search/propose updates
- Notion: search before create
- Slack: read/search/draft, no unsupervised sending
- Sheets/Drive: selected files only
- Browser: fallback only for authenticated workflows
- Deepline workspace: Jai workspace only for Deepline activities

## Stop Conditions

Stop and ask for approval when:

- sending email
- posting content
- modifying CRM records
- deleting anything
- changing auth/secrets
- running a bulk workflow
- using a private transcript externally
- enabling new mutating MCP tools
- bypassing Deepline for provider execution that Deepline can run and observe
