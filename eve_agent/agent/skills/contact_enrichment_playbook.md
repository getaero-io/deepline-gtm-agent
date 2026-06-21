---
description: Use when the user asks to find, verify, enrich, or validate contacts, emails, LinkedIn URLs, titles, or prospect lists.
---

# Contact Enrichment Playbook

Use Deepline enrichment and verification paths through `deepline_chat`. For one explicitly named Deepline tool and payload, use `deepline_execute_tool`.

## Procedure

1. Capture the identity inputs: person name, company, domain, title, region, and any known email or LinkedIn URL.
2. Prefer a minimal enrichment path before broad provider fan-out.
3. For email discovery, verify deliverability before recommending use.
4. For LinkedIn or title resolution, report confidence and source/provider status.
5. For lists, run a pilot sample first and stop for approval before full enrichment.

## Safety Rules

- Do not fabricate contact data.
- Do not mark an email safe unless Deepline/provider verification supports it.
- Do not export or enroll a full list without explicit approval.
- Report provider gaps, credential errors, and ambiguous matches plainly.

## Output Shape

- Found data with confidence
- Verification status
- Source/provider outcome
- Gaps or ambiguity
- Recommended next step
