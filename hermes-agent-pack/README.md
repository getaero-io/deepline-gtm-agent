# Deepline Hermes GTM Agent

Branch: `deepline-gtm-agent`

This repo is a lightweight operating pack for running a Deepline-specific GTM agent in Hermes.

It is intentionally narrow. Hermes should be the operator interface; Deepline should be the GTM access, execution, logging, and observability layer. The agent should not ingest the whole transcripts repo, the whole CRM, or every strategy file. It should start with a few high-signal context files, use Deepline-native runs for GTM work, and add extra MCPs only when they are clearly needed.

## What This Repo Contains

- `deck/deepline-hermes-gtm-agent-deck.html` - standalone HTML deck for presenting the setup.
- `context/` - pruned Deepline context that Hermes should read first.
- `prompts/` - copy/paste prompts to seed Hermes, launch the GTM operator, and run workflows.
- `connectors/` - recommended connector manifest and MCP policy.
- `rules/` - operating rules for safe GTM agent behavior.
- `skills/` - Hermes-compatible `SKILL.md` packs for the primary GTM operator, bounded subagent workflows, and split marketing specialists.
- `scripts/` - setup helpers for Hermes MCPs and Sprite deployment.
- `sprites/` - notes for the `spawn-k2qb` Sprites instance.
- `docs/research_backed_setup.md` - current research-backed setup matrix for GTM agents.

## Setup Principles

For GTM workflows, use Deepline first:

```bash
deepline session start --steps '["Inspect request","Select Deepline path","Run pilot","Validate output","Prepare draft"]' --user-prompt "..."
deepline session status --message "Searching Deepline tools for the right provider path"
deepline tools search --categories company_search --search_terms "structured filters,icp"
deepline enrich --input <csv> --output <csv> --rows 0:1 ...
deepline session usage --json
```

Deepline gives the agent provider access, enrichment routing, workflow execution, Session UI progress, logs, usage, and output lineage. Hermes MCPs should not duplicate that surface.

For non-Deepline sidecar actions, current Hermes docs recommend installing MCPs from the curated catalog where possible:

```bash
hermes mcp
hermes mcp catalog
hermes mcp install <name>
hermes mcp configure <name>
```

Hermes supports tool pruning during MCP install/configure. Use it. Only expose tools the agent needs for the current workflow. Do not enable broad delete/admin tools by default.

Sources used while designing this repo:

- Hermes MCP feature docs: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mcp.md
- Hermes repo and release train: https://github.com/NousResearch/hermes-agent
- Sprites CLI docs: https://docs.sprites.dev/cli/installation/
- Sprites quickstart: https://docs.sprites.dev/quickstart/
- Sprites remote MCP docs: https://docs.sprites.dev/integrations/remote-mcp/
- Composio Hermes setup: https://composio.dev/hermes

## Recommended First Hour

1. Copy this repo into the Hermes workspace on `spawn-k2qb`.
2. Ask Hermes to read only:
   - `context/deepline_gtm_context.md`
   - `context/claims_and_exclusions.md`
   - `context/jai_voice_and_copy_rules.md`
   - `rules/agent_operating_rules.md`
   - `connectors/connector_manifest.yaml`
3. Confirm Deepline CLI/API access and the Jai workspace.
4. Start a Deepline Session UI plan for the first workflow.
5. Install only sidecar connectors needed beyond Deepline.
6. Run the general GTM Agent seed prompt.
7. Run the split Marketing Agents seed prompt.
8. Set up AgentMail as the agent-owned inbox after Telegram/Deepline are stable.
9. Execute one safe draft-only workflow:
   - post-call follow-up draft, or
   - account research brief, or
   - LinkedIn post draft from a transcript.

## Safety Defaults

- Draft before send.
- Read before write.
- Search before create.
- Never fabricate proof points.
- Never quote transcript content externally unless the quote is in `claims_and_exclusions.md` and marked usable.
- Never include Benjamin Reed or Alfie Carter in Deepline marketing content.
- Keep secrets outside Markdown files.
- Prefer Deepline-native GTM execution over MCP/tool sprawl.
- Prefer scoped APIs/MCP tools over browser automation when Deepline is not the right owner.
- Use AgentMail for agent identity/inbound/drafts, not unsupervised outbound.
- Do not connect the entire transcripts folder. Pull relevant excerpts into `context/source_notes/` only after review.

## Sprite Target

The intended Sprites instance is:

```text
spawn-k2qb
```

Use:

```bash
sprite use spawn-k2qb
sprite exec -- pwd
```

If `sprite` is not installed:

```bash
curl -fsSL https://sprites.dev/install.sh | sh
```
