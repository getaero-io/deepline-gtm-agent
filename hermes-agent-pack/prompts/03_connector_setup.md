# Prompt: Connector Setup In Hermes

```text
You are setting up connectors for the Deepline Hermes GTM Agent.

Read:

- connectors/connector_manifest.yaml
- rules/agent_operating_rules.md

First confirm Deepline-native access:

deepline --version
deepline tools search --categories admin --search_terms "logs,usage,session"
deepline session usage --json

Treat Deepline as the primary access, execution, logging, and observability layer for GTM work.

Then inspect the current Hermes MCP catalog only for sidecar needs:

hermes mcp catalog

Recommend the smallest connector set for these first workflows:

1. post-call follow-up draft
2. account research brief
3. LinkedIn post draft from approved context
4. CRM hygiene suggestions

For each connector, specify:

- why it is needed
- why Deepline cannot or should not own that action
- whether it should be MCP, direct API, or script
- which tools/scopes to enable
- which tools/scopes to disable
- first safe test

Do not install mutating tools until I approve. Do not duplicate Deepline provider access through separate MCPs.
```
