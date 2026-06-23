---
description: Use when the user asks what Deepline GTM workflows are available, asks which preset to use, or wants to design a repeatable GTM workflow.
---

# Workflow Preset Selection

Use the workflow preset tools to select a repeatable GTM workflow.

## Procedure

1. Call `list_workflow_presets` when the user asks what workflows are available or describes an unclear workflow.
2. Match the user request to one or two likely presets.
3. Call `get_workflow_preset` for the selected preset when the user asks for details or implementation guidance.
4. Explain required inputs, tool bounds, approval gates, and expected output.
5. Recommend the smallest pilot that proves the workflow before scaling it.

## Selection Heuristics

- Contact/list work: enrichment or bounded tool action presets
- Account briefs: account digest or web context research
- Support triage: self-serve support agent
- Multi-step GTM execution: closed-loop GTM workflow
- Warehouse questions: Snowflake query agent

Do not skip approval gates embedded in a preset.
