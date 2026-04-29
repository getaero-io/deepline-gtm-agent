# Building a Production GTM Agent: What We Learned

We built a GTM (go-to-market) agent that connects to 441+ sales and marketing tools. Here's what worked, what didn't, and what we'd do differently.

## The Architecture

Two implementations running in parallel:

1. **LangGraph agent** - Uses Deep Agents framework with LangChain tools
2. **Managed Agent** - Anthropic's managed agent sandbox with CLI-based tool execution

Both share the same Deepline tool catalog and skill docs. The managed agent runs tools via subprocess in a sandboxed container; the LangGraph version calls the Deepline HTTP API directly.

## What Worked Well

### 1. Claude Code optimizations transferred directly

Our existing Claude Code patterns - waterfall enrichment, tool catalogs, provider playbooks - worked out of the box. The local skill docs we'd built for Claude Code gave the agent exactly the context it needed to pick the right tools.

Key patterns that carried over:
- Embedding the full tool catalog in the `deepline_call` tool description
- Waterfall functions that exhaust multiple providers before giving up
- Structured output formats (person cards, company cards, lists)

### 2. Managed agents sandbox model

The Anthropic managed agent sandbox was surprisingly productive. The agent has a real filesystem, can run CLI commands, and persists state across tool calls. We upload the Deepline CLI binary and auth credentials at session start, then the agent bootstraps itself.

This meant zero custom tool definitions. The agent just runs `deepline tools execute <tool_id> --payload '...'` and parses the JSON output. Every tool in the Deepline catalog works automatically.

### 3. Skill docs as context

We host skill docs on a CDN and fetch them at session startup. The agent gets ~300KB of context about how to use each provider, common patterns, and exact tool IDs. This eliminated most hallucination about tool names and parameters.

```
SKILLS_BASE = "https://code.deepline.com/.well-known/skills/gtm-meta-skill"
CORE_SKILL_DOCS = [
    "SKILL.md",
    "finding-companies-and-contacts.md",
    "enriching-and-researching.md",
    "provider-playbooks/apollo.md",
    "provider-playbooks/hubspot.md",
    ...
]
```

## What Didn't Work

### 1. Slack interactivity was the hardest part

We spent more time debugging Slack formatting than the actual agent logic. Issues:

**Two different markdown converters**: We had one `md_to_slack()` in the LangGraph version and another in the managed agent version. They had different capabilities and produced inconsistent output.

**Headers getting glued to text**: The agent emits multiple text blocks. When they concatenate, you get `Done.## Next Steps` instead of proper separation.

**Verbose output**: Despite prompting for concise responses, the agent would explain what it was doing: "I'll now search for..." followed by the actual search, followed by "I found..." followed by the results.

**Table rendering**: Markdown tables don't render in Slack. We built a converter, but it was brittle.

### 2. Event deduplication memory leak

Our dedup cache cleared entirely when it hit 10K entries:

```python
if len(_seen_event_ids) > 10_000:
    _seen_event_ids.clear()  # Bad!
```

The brief window after clear could cause duplicate event processing if Slack retried. Fixed with LRU eviction instead.

### 3. Blocking I/O in async context

The LangGraph version's tool functions were synchronous, but called from an async FastAPI server. Every `deepline_execute()` call blocked the event loop. With multiple concurrent Slack requests, they queued behind each other.

### 4. No timeout on tool calls

If a Deepline tool hung (network issues, slow provider), the entire agent session hung indefinitely. We added timeouts and retry logic.

## What We'd Do Differently

### 1. Use Vercel AI SDK for the Slack layer

The Slack bot code was 40% of our total codebase and 80% of the bugs. Streaming text to Slack, handling reconnects, formatting markdown - all of this is solved by the Vercel AI SDK's chat completion streaming.

If we rebuilt today:
- **Agent layer**: Keep the managed agent / LangGraph core. This part works great.
- **Chat UI layer**: Replace the custom Slack bot with Vercel AI SDK + a thin Slack adapter.

The agent's job is calling tools and reasoning. The UI layer's job is presenting that to users. Mixing them created coupling that made both harder to maintain.

### 2. Default to Opus for planning

For simple enrichment requests, Sonnet is fine. But for complex multi-step workflows (build a TAM list, research 20 companies, add qualified leads to Instantly), Opus plans better and makes fewer tool-call mistakes.

We'd offer:
- Sonnet for quick lookups (default for `/enrich`, `/search`)
- Opus for planning workflows (default for `/build`, `/research`)

### 3. Structured output, not free text

The agent returns free-form markdown. For GTM data (emails, phone numbers, LinkedIn URLs), this is fragile. A typo in the output format means broken parsing downstream.

We'd use structured output (JSON) for data and only use markdown for human-readable summaries.

### 4. Cost tracking per request

Deepline operations consume credits, but we had no per-request cost tracking. Users would burn through their quota on expensive waterfall enrichments without visibility.

We'd add:
- Credit cost estimate before execution
- Running total in the response
- Budget limits per session/user

## Cost Optimizations from Claude Code

We borrowed several patterns from the Claude Code open source:

### Truncate large tool results

```python
MAX_TOOL_RESULT_CHARS = 8000
PREVIEW_SIZE = 2000

def truncate_tool_result(result):
    if isinstance(result, str) and len(result) > MAX_TOOL_RESULT_CHARS:
        return f"{result[:PREVIEW_SIZE]}\n\n... (truncated, {len(result)} chars total)"
    # Handle dicts/lists similarly
```

### Short error stacks

```python
def short_error_stack(e, max_frames=5):
    """5 frames is usually enough to debug. Save tokens."""
```

### Skill budget constraints

Claude Code caps skill descriptions at 1% of context window and truncates individual descriptions to ~250 chars. We were embedding 300KB of skill docs - way over budget.

## The Numbers

After fixes:
- **Slack formatting bugs**: 0 (down from 4-5 per week)
- **Duplicate event processing**: 0 (was ~1% of events)
- **Tool timeout errors**: 0 (was ~2% of requests)
- **Average response time**: 8s (down from 12s with retry logic and parallel tool calls)

## Conclusion

The agent layer was the easy part. Claude + good context + well-designed tools = a capable agent.

The hard part was the last mile: presenting agent output in a chat UI, handling streaming, formatting for different clients, error recovery. This is not agent-specific - it's chat infrastructure.

Next time, we'd build the agent as a pure API (JSON in, JSON out) and use battle-tested chat infrastructure (Vercel AI SDK, stream.ai, etc.) for the UI layer.

---

*Built with [Deepline](https://code.deepline.com) and [Claude Code](https://claude.ai/claude-code)*
