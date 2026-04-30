# Building a Production GTM Agent

We built a GTM agent that connects to 441 sales and marketing tools. Shipped it to Slack. Spent 80% of our time on Slack formatting bugs.

The agent logic worked fine. The chat layer took four weeks of edge cases.

## Architecture

Two implementations running in parallel:

1. **LangGraph agent** - Deep Agents framework with LangChain tools
2. **Managed Agent** - Anthropic sandbox with CLI tool execution

Both use the same Deepline tool catalog. The managed agent runs `deepline tools execute <tool_id> --payload '{...}'` via subprocess. LangGraph calls the HTTP API directly.

## What worked

**Claude Code patterns transferred.** Waterfall enrichment, tool catalogs, provider playbooks - all worked out of the box. The skill docs we'd built for Claude Code gave the agent exactly the context it needed.

Key patterns:
- Full tool catalog embedded in the `deepline_call` description
- Waterfall functions that exhaust multiple providers before failing
- Structured output formats (person cards, company cards)

**The sandbox model is good.** Real filesystem, CLI access, persistent state. We upload the Deepline binary at session start. Every tool works automatically with zero custom definitions.

**Skill docs eliminate hallucination.** 300KB of context about provider patterns and exact tool IDs, fetched from CDN at startup.

```
SKILLS_BASE = "https://code.deepline.com/.well-known/skills/gtm-meta-skill"
CORE_SKILL_DOCS = [
    "SKILL.md",
    "finding-companies-and-contacts.md",
    "provider-playbooks/apollo.md",
    ...
]
```

## What broke

**Slack formatting.** We spent more time debugging mrkdwn than agent logic.

Two markdown converters with different behavior. Headers glued to preceding text (`Done.## Next Steps`). Verbose narration ("I'll search for..." before every action). Markdown tables that Slack doesn't render.

**Memory leak in dedup cache.** We cleared the whole cache at 10K entries:

```python
if len(_seen_event_ids) > 10_000:
    _seen_event_ids.clear()  # Wrong
```

Brief window after clear meant duplicate events if Slack retried. Fixed with LRU eviction.

**Blocking I/O.** Sync tool functions called from async FastAPI. Every `deepline_execute()` blocked the event loop. Concurrent requests queued behind each other.

**No timeouts.** Slow provider meant hung session. Added 120s timeout and retry logic for read-only operations.

## What we'd change

**Use Vercel AI SDK for chat.** The Slack bot was 40% of the codebase and 80% of the bugs. Streaming, reconnection, formatting - all solved problems we rebuilt from scratch.

If we rebuilt today:
- Keep the managed agent core (it works)
- Replace custom Slack bot with AI SDK + thin adapter

Agents should call tools and reason. Chat layers should present output. We mixed them, and the coupling made both harder to maintain.

**Opus for planning.** Sonnet handles simple enrichments fine. Complex workflows (build TAM, research 20 companies, add to Instantly) need Opus - it plans better and makes fewer tool-call mistakes.

**Structured output for data.** Free-form markdown for GTM data is fragile. JSON for data, markdown for summaries.

**Cost tracking.** We had no visibility into credit consumption per request. Users burned quota on expensive waterfalls without knowing until their balance hit zero.

## Cost patterns from Claude Code

**Truncate large results** (presentation layer only):

```python
MAX_TOOL_RESULT_CHARS = 8000

def truncate_tool_result(result):
    if isinstance(result, str) and len(result) > MAX_TOOL_RESULT_CHARS:
        return f"{result[:2000]}\n\n... ({len(result)} chars total)"
```

**Short error stacks:**

```python
def short_error_stack(e, max_frames=5):
    # 5 frames is enough. Save tokens.
```

**Skill budget.** Claude Code caps skill descriptions at 1% of context. We were embedding 300KB - way over budget.

## After fixes

- Formatting bugs: 0 (was 4-5/week)
- Duplicate events: 0 (was ~1%)
- Timeout errors: 0 (was ~2%)
- Response time: 8s (was 12s)

## The lesson

Agent logic was easy. Claude with good context and well-designed tools makes a capable agent.

Chat infrastructure was hard. Streaming, formatting, reconnection, error recovery - none of this is agent-specific. It's plumbing that every chat app needs.

Build the agent as a pure API. Use battle-tested chat infrastructure for the UI.

---

*Built with [Deepline](https://code.deepline.com) and [Claude Code](https://claude.ai/claude-code)*
