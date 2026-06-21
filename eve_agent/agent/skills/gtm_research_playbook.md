---
description: Use when the user asks for account research, market research, web context, trigger discovery, or GTM-relevant company analysis.
---

# GTM Research Playbook

Use Deepline as the execution backend for research. Prefer `deepline_chat` unless the user explicitly asks for a bounded direct tool call.

## Procedure

1. Clarify the target entity: company, domain, account list, segment, buyer, or market.
2. Ask Deepline for source-backed research, not generic synthesis.
3. Separate confirmed facts from inferred GTM signals.
4. Identify the buying context: business model, likely ICP fit, active initiatives, hiring, product motion, tech stack, and recent events.
5. Return a concise account brief with sources, confidence, gaps, and recommended next action.

## Output Shape

- Account or segment summary
- Source-backed signals
- Buyer or persona implications
- Outreach or workflow recommendation
- Missing data and safe next step

Do not invent funding, headcount, executive names, emails, CRM records, or provider results.
