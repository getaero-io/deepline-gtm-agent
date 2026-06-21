---
description: Use when the user asks about CRM hygiene, Salesforce, HubSpot, account/contact updates, dedupe, ownership, lifecycle stage, or pipeline data.
---

# CRM Safety Rules

CRM work must be source-backed, reversible where possible, and approval-gated for writes.

## Read Before Write

1. Identify the CRM system and object type.
2. Fetch or ask Deepline to fetch the relevant records first.
3. Check for duplicates and ownership conflicts.
4. Compare proposed updates against current values.
5. Present a diff before asking for approval.

## Never Do Automatically

- Overwrite owner, lifecycle stage, pipeline stage, or source fields without approval.
- Create duplicate contacts or accounts when a likely match exists.
- Merge records without an explicit merge plan.
- Write inferred data as confirmed fact.

## Output Shape

- Records inspected
- Current values
- Proposed changes
- Risk notes
- Approval request or safe read-only recommendation
