"""View Managed Agent session logs.

Usage:
    python logs.py                          # list recent sessions
    python logs.py sesn_...                 # show full event log for a session
    python logs.py sesn_... --raw           # dump raw JSON events
"""

import json
import sys

import anthropic


def list_sessions(client: anthropic.Anthropic, limit: int = 20) -> None:
    sessions = client.beta.sessions.list()
    print(f"{'Session ID':<42} {'Status':<14} {'Title'}")
    print("-" * 100)
    for s in sessions.data[:limit]:
        title = getattr(s, "title", "") or ""
        print(f"{s.id:<42} {s.status:<14} {title[:60]}")


def show_session(client: anthropic.Anthropic, session_id: str, raw: bool = False) -> None:
    session = client.beta.sessions.retrieve(session_id=session_id)
    print(f"Session:  {session.id}")
    print(f"Status:   {session.status}")
    print(f"Title:    {getattr(session, 'title', '')}")
    usage = getattr(session, "usage", None)
    if usage:
        print(f"Tokens:   in={getattr(usage, 'input_tokens', 0):,}  out={getattr(usage, 'output_tokens', 0):,}")
    print("-" * 80)

    events = client.beta.sessions.events.list(session_id=session_id)
    for e in events.data:
        if raw:
            print(json.dumps(e.model_dump(), indent=2, default=str))
            continue

        t = e.type
        ts_raw = getattr(e, "processed_at", None)
        if ts_raw is None:
            ts_short = ""
        elif isinstance(ts_raw, str):
            ts_short = ts_raw[11:19] if len(ts_raw) > 19 else ""
        else:
            ts_short = str(ts_raw)[11:19]

        if t == "user.message":
            for b in getattr(e, "content", []):
                if getattr(b, "type", None) == "text":
                    print(f"  {ts_short} [user] {b.text[:200]}")

        elif t == "agent.message":
            for b in getattr(e, "content", []):
                if getattr(b, "type", None) == "text":
                    print(f"  {ts_short} [agent] {b.text[:200]}")

        elif t == "agent.tool_use":
            name = getattr(e, "name", "?")
            inp = getattr(e, "input", {})
            if name == "bash":
                cmd = inp.get("command", "")[:150]
                print(f"  {ts_short} [bash] $ {cmd}")
            elif name in ("read", "write", "edit"):
                path = inp.get("file_path", "") or inp.get("path", "")
                print(f"  {ts_short} [{name}] {path}")
            elif name in ("glob", "grep"):
                pattern = inp.get("pattern", "")
                print(f"  {ts_short} [{name}] {pattern}")
            else:
                print(f"  {ts_short} [{name}]")

        elif t == "agent.tool_result":
            pass  # Usually too verbose

        elif t.startswith("session.status"):
            status = t.split("session.status_")[-1] if "status_" in t else t
            reason = ""
            sr = getattr(e, "stop_reason", None)
            if sr:
                reason = f" ({getattr(sr, 'type', '')})"
            print(f"  {ts_short} --- {status}{reason} ---")

        elif t == "span.model_request_end":
            usage = getattr(e, "model_usage", None)
            if usage:
                i = getattr(usage, "input_tokens", 0)
                o = getattr(usage, "output_tokens", 0)
                cr = getattr(usage, "cache_read_input_tokens", 0)
                print(f"  {ts_short} [tokens] in={i:,} out={o:,} cache_read={cr:,}")

        elif t == "agent.thread_context_compacted":
            print(f"  {ts_short} [compacted]")


def main() -> None:
    client = anthropic.Anthropic()
    args = sys.argv[1:]

    if not args:
        list_sessions(client)
        return

    session_id = args[0]
    raw = "--raw" in args
    show_session(client, session_id, raw=raw)


if __name__ == "__main__":
    main()
