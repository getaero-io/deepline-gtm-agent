---
name: deepline-proof-guard
description: Use before publishing Deepline claims, proof points, stats, customer references, or competitive statements. Blocks unsupported claims and excluded names.
---

# Deepline Proof Guard Skill

## Trigger

Use this before any outbound, marketing, sales, deck, newsletter, or social artifact that includes:

- metrics
- customer references
- competitor comparisons
- implementation timelines
- ROI or coverage claims
- transcript-derived claims

## Required Context

Read first:

- `context/claims_and_exclusions.md`
- `context/deepline_gtm_context.md`
- `rules/agent_operating_rules.md`

## Rules

- Never include Benjamin Reed or Alfie Carter.
- Never invent proof.
- Mark unsupported claims as `needs review`.
- If a claim is not explicitly approved, rewrite it as a qualitative positioning point or remove it.
- Preserve source/proof status in the output.

## Output Pattern

- `approved`: safe claims
- `needs review`: claims that need source confirmation
- `blocked`: claims/names that must not be used
- `rewrite`: safer replacement copy
