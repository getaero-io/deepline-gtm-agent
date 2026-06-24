---
description: Use when the user asks what Deepline GTM workflows are available, asks which preset to use, or wants to design a repeatable GTM workflow.
---

# Workflow Preset Selection

Use the workflow preset tools to select a repeatable GTM workflow. Shared Deepline API recipes are the primary source; legacy transcript presets are fallback patterns for agent-shaped workflows that do not map cleanly to an onboarding recipe.

## Procedure

1. Call `list_workflow_presets` when the user asks what workflows are available or describes an unclear workflow.
2. Match the user request to one or two likely presets. Prefer `source: deepline-api-recipe` when it fits.
3. Call `get_workflow_preset` for the selected preset when the user asks for details or implementation guidance.
4. Explain required inputs, slot defaults, tool bounds, approval gates, and expected output.
5. Recommend the smallest pilot that proves the workflow before scaling it.

When listing presets, include each exact preset `id` next to its title. Do not
replace IDs with title-only labels; users need copyable IDs such as
`web_context_research` and `snowflake_query_agent` for follow-up requests.

## Selection Heuristics

- Contact/list work: enrichment or bounded tool action presets
- Account briefs: account digest or web context research
- Support triage: self-serve support agent
- Multi-step GTM execution: closed-loop GTM workflow
- Warehouse questions: Snowflake query agent

Do not edit shared recipe prompts in Eve. Update `deepline-api/src/lib/onboard/recipes.json`, then sync the snapshot.

Do not skip approval gates embedded in a preset.
