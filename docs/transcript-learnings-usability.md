# Transcript Learnings -> Repo Usability Improvements

The talks made one thing obvious: the repo cannot just say "build GTM agents."

It needs to help a user pick the right workflow, constrain the agent, know what output should look like, and understand when to ask a human.

This doc maps transcript lessons to concrete repo usability decisions.

## What Changed In The Repo

| Transcript Learning | Usability Problem | Repo Improvement |
|---|---|---|
| LangChain started with one constrained inbound problem, then expanded. | Users do not know what workflow to start with. | Added `/workflow-presets` with six starter workflows. |
| LangChain saw adoption jump when the agent became two-way in Slack and useful for basic BI questions. | The repo felt like an agent backend, not an operator tool. | Presets now include account digest, Slack/chat, and approval workflows. |
| LangChain learned from rep edits through append-only memory and tracked tool-call trajectories in evals. | Users need examples of what the agent should remember and test. | Presets include expected output, learning signals, and approval rules. |
| AssemblyAI needed control over prompts, tools, RAG, docs, and escalation. | Users need a clear support/onboarding workflow, not just generic chat. | Added a self-serve support/onboarding preset with escalation boundaries. |
| AssemblyAI keeps docs as current markdown and streams visible progress. | Users need the repo docs to be agent-readable and copy-pasteable. | Added Notion-ready markdown, request templates, and output shapes. |
| Exa framed search as web context for agents. | Users may treat search as a link dump. | Added a web-context research preset with source-backed claims, freshness, confidence, and next workflow. |
| Composio emphasized tool search, auth, big tool-call payloads, and integration harnessing. | Users need to bound tools before the agent acts. | Added a bounded tool/action preset and exposed tool bounds in every preset. |
| Deepline showed the context -> action -> insight loop and provider waterfall economics. | Users need a closed-loop GTM example that handles writeback and learning. | Added a closed-loop workflow preset with provider/cost notes and approval before side effects. |

## The Workflow Preset API

Run the broker:

```bash
cd managed_agent
python server.py
```

List the presets:

```bash
curl http://localhost:8000/workflow-presets
```

Get one preset:

```bash
curl http://localhost:8000/workflow-presets/web_context_research
```

Each preset returns:

- `title`
- `speaker_pattern`
- `why`
- `best_for`
- `prompt`
- `suggested_tool_bounds`
- `expected_output`
- `human_approval_required_for`

The goal is to make the repo easier to use from a LinkedIn lead magnet:

1. Comment `AGENTS`.
2. Open the repo.
3. Pick a preset.
4. Run the prompt.
5. Know what good output looks like.

No 40-minute philosophical onboarding. We are all tired.

## Preset Selection Guide

| If You Want To... | Start With |
|---|---|
| Research inbound leads and ask a rep before outreach | `inbound_lead_approval` |
| Give reps a Monday morning account digest | `account_digest` |
| Deflect support/onboarding questions with docs and escalation | `self_serve_support_agent` |
| Turn web search into source-backed GTM context | `web_context_research` |
| Scope tools/actions before an agent touches CRM/Gmail/Slack | `bounded_tool_action` |
| Combine first-party + third-party data into an approved action | `closed_loop_gtm_workflow` |

## What Good Usability Looks Like

Good repo experience:

```text
I know which preset to use.
I can copy the prompt.
I can see suggested tool bounds.
I know what the output should contain.
I know where human approval is required.
I can run it through REST, Slack, or web chat.
```

Bad repo experience:

```text
Here is an agent framework. Good luck.
```

We have all suffered enough.

## Next Usability Improvements

These are the obvious next cuts:

- Add a tiny web UI dropdown for workflow presets.
- Add saved example request JSON files for each preset.
- Add eval fixtures for the expected output shape of each preset.
- Add a `/workflow-presets/{id}/curl` helper if users keep asking for examples.
- Add docs sync guidance so support/onboarding agents can read current markdown like AssemblyAI's Joey pattern.

