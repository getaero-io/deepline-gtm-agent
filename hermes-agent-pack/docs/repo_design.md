# Repo Design

## Why Standalone

Hermes should not start by reading a large, messy workspace. This repo gives it a small, reviewable operating pack.

## File Responsibilities

- `context/` gives durable GTM facts.
- `rules/` gives behavior boundaries.
- `connectors/` tells Hermes which tools are worth connecting and how much scope to expose.
- `prompts/` gives Jai copy/paste startup prompts.
- `skills/` gives Hermes reusable procedures.
- `deck/` explains the system to humans.
- `sprites/` documents the remote runtime.

## Context Pruning Policy

Do not put raw transcripts in this repo by default.

When a workflow needs transcript evidence:

1. extract the smallest relevant quote or summary
2. record source filename/date/speaker
3. mark whether it is usable externally
4. add it to `context/source_notes/`

## Agent Profile

Start with one focused profile: `deeplinegtm`.

Inside that profile, use one primary operator skill and bounded subagent skills:

- Deepline GTM Agent
- Sales Workflows Subagent
- Proof Guard
- Account Research Agent
- CRM Hygiene Agent
- AgentMail Inbox Agent
- Workflow Spec Agent

Marketing is split out as separate specialists because content, campaign planning, and proof review need different constraints:

- Marketing Content Agent
- Marketing Campaign Agent
- Marketing Proof Agent

## First Branch

The feature branch is:

```text
deepline-gtm-agent
```
