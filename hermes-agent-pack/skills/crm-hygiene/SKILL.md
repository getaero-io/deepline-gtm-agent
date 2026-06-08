---
name: deepline-crm-hygiene
description: Use for HubSpot/CRM hygiene proposals, duplicate checks, missing-field audits, stale deal review, and proposed CRM updates. Proposal-only unless approved.
---

# Deepline CRM Hygiene Skill

## Rules

- Search before create.
- Propose before update.
- Never modify CRM records without explicit approval.
- Use Deepline for enrichment, validation, and output lineage.
- Use HubSpot only for approved read/search/propose-update tasks.

## Workflow

1. Identify the CRM object type: contact, company, deal, note, task.
2. Search for existing records before proposing creation.
3. Use Deepline-native enrichment or validation when external GTM data is needed.
4. Produce a proposed change set.
5. Mark confidence and source for each proposed update.

## Output Pattern

- record
- current state
- proposed change
- reason
- source
- confidence
- approval required
