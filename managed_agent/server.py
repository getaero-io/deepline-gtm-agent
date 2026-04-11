"""
FastAPI server — Deepline GTM Managed Agent

Bridges Slack, REST, and Web UI to Anthropic Managed Agent sessions.
Each request spins up a fresh sandbox with the deepline CLI pre-loaded.

Endpoints:
  GET  /health          - health check
  GET  /                - web chat UI
  POST /chat            - single-turn, full response
  POST /chat/stream     - streaming SSE
  POST /slack/events    - Slack Events API webhook
  GET  /slack/oauth_redirect - Slack OAuth callback
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import re

import anthropic
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from session import create_session, send_message, stream_events, BOOTSTRAP_MSG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("API_KEY", "")
_bearer = HTTPBearer(auto_error=False)


async def require_api_key(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    if _API_KEY and (not credentials or credentials.credentials != _API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Deepline GTM Managed Agent server starting")
    # Pre-fetch skill docs from CDN so they're cached for all sessions
    from session import fetch_skill_docs_from_cdn
    docs = fetch_skill_docs_from_cdn()
    logger.info("Pre-fetched %d skill docs from CDN", len(docs))
    yield


app = FastAPI(title="Deepline GTM Managed Agent", version="1.0.0", lifespan=lifespan)

_cors_raw = os.environ.get("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_raw.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    bootstrap: bool = True


class ChatResponse(BaseModel):
    reply: str
    session_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    config_ok = bool(os.environ.get("MANAGED_AGENT_ID") and os.environ.get("MANAGED_ENVIRONMENT_ID"))
    if not config_ok:
        from session import CONFIG_PATH
        config_ok = CONFIG_PATH.exists()
    return {
        "status": "ok" if config_ok else "needs setup",
        "agent": "deepline-gtm-managed-agent",
        "config": "loaded" if config_ok else "set MANAGED_AGENT_ID + MANAGED_ENVIRONMENT_ID or run setup.py",
        "slack": "configured" if os.environ.get("SLACK_BOT_TOKEN") else "not configured",
    }


@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    html_path = Path(__file__).parent / "chat.html"
    if html_path.exists():
        return html_path.read_text()
    return "<h2>Deepline GTM Agent</h2><p>POST to /chat or /chat/stream</p>"


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    client = get_client()
    loop = asyncio.get_event_loop()

    def _run():
        session_id = create_session(client, title=req.message[:60])
        prompt = f"{BOOTSTRAP_MSG}\n\nThen: {req.message}" if req.bootstrap else req.message
        send_message(client, session_id, prompt)

        parts = []
        for evt in stream_events(client, session_id):
            if evt["type"] == "text":
                parts.append(evt["text"])
        return "".join(parts), session_id

    reply, session_id = await loop.run_in_executor(None, _run)
    return ChatResponse(reply=reply, session_id=session_id)


@app.post("/chat/stream", dependencies=[Depends(require_api_key)])
async def chat_stream(req: ChatRequest):
    client = get_client()

    async def generate() -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()

        session_id = await loop.run_in_executor(
            None, create_session, client, req.message[:60]
        )
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"

        prompt = f"{BOOTSTRAP_MSG}\n\nThen: {req.message}" if req.bootstrap else req.message
        await loop.run_in_executor(None, send_message, client, session_id, prompt)

        def _stream():
            return list(stream_events(client, session_id))

        events = await loop.run_in_executor(None, _stream)
        for evt in events:
            yield f"data: {json.dumps(evt)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

def md_to_slack(text: str) -> str:
    """Convert GitHub-flavored Markdown to Slack mrkdwn.

    Handles: headers, bold, italic, strikethrough, links, lists, blockquotes,
    horizontal rules, code blocks, and markdown tables.
    """
    # --- Preserve code blocks (don't convert inside them) ---
    code_blocks: list[str] = []

    def _stash_code(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    text = re.sub(r"```[\s\S]*?```", _stash_code, text)

    # --- Tables → formatted text blocks ---
    # Match both |col|col| style AND col | col | col style tables.
    def _is_separator(line: str) -> bool:
        """Check if a line is a markdown table separator like |---|---| or ---|---"""
        stripped = line.strip().strip("|").strip()
        return bool(re.match(r"^[\s\-:|]+$", stripped)) and "---" in stripped

    def _convert_table(m: re.Match) -> str:
        lines = [l.strip() for l in m.group(0).strip().split("\n") if l.strip()]
        rows = []
        for line in lines:
            if _is_separator(line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append(cells)
        if not rows:
            return m.group(0)

        headers = rows[0]
        data_rows = rows[1:]

        # For small tables (<=3 cols), use key:value pairs
        if len(headers) <= 3 and data_rows:
            parts = []
            for row in data_rows:
                pair = " | ".join(
                    f"*{headers[i]}:* {row[i]}" if i < len(headers) else row[i]
                    for i in range(len(row))
                )
                parts.append(pair)
            return "\n".join(parts)

        # For wider tables: bold header row + data rows
        parts = [" | ".join(f"*{h}*" for h in headers)]
        for row in data_rows:
            parts.append(" | ".join(row))
        return "\n".join(parts)

    # Match tables with | at edges
    text = re.sub(
        r"(?:^\|.+\|$\n?){2,}",
        _convert_table,
        text,
        flags=re.MULTILINE,
    )
    # Match tables WITHOUT | at edges (e.g. "col1 | col2 | col3\n---|---\nval | val")
    text = re.sub(
        r"(?:^[^\n|]+\|[^\n]+$\n?){2,}",
        _convert_table,
        text,
        flags=re.MULTILINE,
    )

    # --- Headers: ## Title → *Title* ---
    # Match # headers but NOT lines that look like table rows (contain |)
    def _convert_header(m: re.Match) -> str:
        content = m.group(2)
        if "|" in content:
            return m.group(0)  # table row, not a header
        return f"*{content}*"

    text = re.sub(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$", _convert_header, text, flags=re.MULTILINE)

    # --- Bold: **text** → *text* ---
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"*\1*", text)
    text = re.sub(r"__([^_\n]+)__", r"*\1*", text)

    # --- Strikethrough: ~~text~~ → ~text~ ---
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)

    # --- Links: [text](url) → <url|text> ---
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

    # --- Horizontal rules → blank line ---
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # --- Blockquotes: > text → text (Slack doesn't render these) ---
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # --- Unordered lists: - item → • item ---
    text = re.sub(r"^[ \t]*[-*]\s+", "• ", text, flags=re.MULTILINE)

    # --- Restore code blocks ---
    for i, block in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{i}__", block)

    # --- Collapse excessive blank lines ---
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")

# Per-workspace tokens populated via OAuth.
_workspace_tokens: dict[str, str] = {}


def _verify_slack_sig(body: bytes, timestamp: str, signature: str) -> bool:
    if not SLACK_SIGNING_SECRET:
        return True
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - ts) > 300:
        return False
    base = f"v0:{timestamp}:{body.decode()}".encode()
    expected = "v0=" + hmac.new(SLACK_SIGNING_SECRET.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _slack_post(channel: str, text: str, token: str, thread_ts: str | None = None):
    import httpx
    payload = {"channel": channel, "text": text, "mrkdwn": True}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    async with httpx.AsyncClient() as http:
        await http.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10,
        )


async def _slack_react(channel: str, ts: str, emoji: str, token: str, remove: bool = False):
    import httpx
    endpoint = "reactions.remove" if remove else "reactions.add"
    try:
        async with httpx.AsyncClient() as http:
            await http.post(
                f"https://slack.com/api/{endpoint}",
                headers={"Authorization": f"Bearer {token}"},
                json={"channel": channel, "timestamp": ts, "name": emoji},
                timeout=10,
            )
    except Exception:
        pass


async def _fetch_thread_history(channel: str, thread_ts: str, token: str, limit: int = 20) -> list[dict]:
    """Fetch recent messages from a Slack thread for context."""
    import httpx
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                "https://slack.com/api/conversations.replies",
                headers={"Authorization": f"Bearer {token}"},
                params={"channel": channel, "ts": thread_ts, "limit": limit},
                timeout=10,
            )
        data = resp.json()
        if not data.get("ok"):
            return []
        messages = []
        for msg in data.get("messages", [])[:-1]:  # exclude the current message (last)
            text = msg.get("text", "").strip()
            if text.startswith("<@"):
                text = text.split(">", 1)[-1].strip()
            if not text:
                continue
            role = "assistant" if msg.get("bot_id") else "user"
            messages.append({"role": role, "content": text})
        return messages
    except Exception as e:
        logger.warning("Failed to fetch thread history: %s", e)
        return []


async def _handle_slack_event(event: dict, team_id: str):
    """Process a Slack message via a Managed Agent session."""
    token = _workspace_tokens.get(team_id, SLACK_BOT_TOKEN)
    channel = event.get("channel", "")
    user_text = event.get("text", "").strip()
    if user_text.startswith("<@"):
        user_text = user_text.split(">", 1)[-1].strip()
    if not user_text:
        return

    message_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts") or message_ts
    user_id = event.get("user", "")

    logger.info("Slack: processing message from %s: %.80s", user_id, user_text)
    await _slack_react(channel, message_ts, "eyes", token)

    # Fetch thread history for context (if this is a reply in a thread)
    thread_context = ""
    if event.get("thread_ts"):
        history = await _fetch_thread_history(channel, thread_ts, token)
        if history:
            lines = []
            for msg in history:
                prefix = "User" if msg["role"] == "user" else "Agent"
                lines.append(f"{prefix}: {msg['content']}")
            thread_context = (
                "\n\n## Thread context (previous messages in this Slack thread):\n"
                + "\n\n".join(lines)
                + "\n\n## Current message:\n"
            )
            logger.info("Slack: fetched %d prior messages from thread", len(history))

    session_id = None
    try:
        client = get_client()
        loop = asyncio.get_event_loop()

        logger.info("Slack: creating session...")
        session_id = await loop.run_in_executor(
            None, create_session, client, f"Slack: {user_text[:50]}"
        )
        logger.info("Slack: session %s created, sending message", session_id)

        prompt = f"{BOOTSTRAP_MSG}\n\n{thread_context}Then: {user_text}"
        await loop.run_in_executor(None, send_message, client, session_id, prompt)

        def _collect():
            parts = []
            for evt in stream_events(client, session_id):
                if evt["type"] == "text":
                    parts.append(evt["text"])
                elif evt["type"] == "done":
                    logger.info("Slack: session %s done (%s)", session_id, evt.get("reason"))
            # The agent emits multiple text blocks. If consecutive blocks don't
            # end/start with newlines, headers get glued to preceding text
            # (e.g. "Done.## Title"). Fix by ensuring block boundaries have spacing.
            merged = "".join(parts)
            # Insert newline before markdown headers that follow non-whitespace.
            # Use negative lookbehind to avoid splitting ## into # + #
            merged = re.sub(r"([^\n#])(#{1,6}\s)", r"\1\n\n\2", merged)
            return merged

        logger.info("Slack: streaming events for session %s...", session_id)
        reply = await loop.run_in_executor(None, _collect)
        logger.info("Slack: got reply (%d chars) for session %s", len(reply or ""), session_id)

        await _slack_react(channel, message_ts, "eyes", token, remove=True)
        slack_reply = md_to_slack(reply) if reply else "(no response)"

        # Slack limits messages to ~4000 chars. Split if needed.
        if len(slack_reply) <= 3900:
            await _slack_post(channel, slack_reply, token, thread_ts)
        else:
            chunks = []
            current = ""
            for para in slack_reply.split("\n\n"):
                if len(current) + len(para) + 2 > 3900:
                    chunks.append(current.strip())
                    current = para
                else:
                    current = current + "\n\n" + para if current else para
            if current.strip():
                chunks.append(current.strip())
            for chunk in chunks:
                await _slack_post(channel, chunk, token, thread_ts)
        logger.info("Slack: reply posted for session %s", session_id)
    except Exception as e:
        logger.exception("Slack handler error (session=%s)", session_id)
        try:
            await _slack_react(channel, message_ts, "eyes", token, remove=True)
            await _slack_post(channel, f":warning: Error: {e}", token, thread_ts)
        except Exception:
            logger.exception("Failed to send error message to Slack")


_seen_events: set[str] = set()


@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400)

    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    if not _verify_slack_sig(
        body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    ):
        return Response(status_code=403)

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_id = payload.get("event_id", "")
        etype = event.get("type", "")
        ctype = event.get("channel_type", "")

        if event_id in _seen_events:
            return Response(status_code=200)
        _seen_events.add(event_id)
        if len(_seen_events) > 10_000:
            _seen_events.clear()

        if event.get("bot_id") or event.get("subtype"):
            return Response(status_code=200)

        if etype == "app_mention" or (etype == "message" and ctype == "im"):
            team_id = payload.get("team_id", "")
            background_tasks.add_task(_handle_slack_event, event, team_id)

    return Response(status_code=200)


@app.get("/slack/oauth_redirect")
async def slack_oauth_redirect(code: str = "", error: str = ""):
    import httpx
    if error:
        return HTMLResponse(f"<h2>OAuth error: {error}</h2>", status_code=400)
    if not code:
        return HTMLResponse("<h2>Missing code</h2>", status_code=400)

    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return HTMLResponse("<h2>Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET</h2>", status_code=500)

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://slack.com/api/oauth.v2.access",
            data={"client_id": client_id, "client_secret": client_secret, "code": code},
            timeout=10,
        )
    data = resp.json()
    if not data.get("ok"):
        return HTMLResponse(f"<h2>OAuth failed: {data.get('error')}</h2>", status_code=400)

    bot_token = data.get("access_token", "")
    team_id = data.get("team", {}).get("id", "")
    team_name = data.get("team", {}).get("name", "workspace")
    if team_id and bot_token:
        _workspace_tokens[team_id] = bot_token

    return HTMLResponse(f"""<!DOCTYPE html>
<html><body style="font-family:system-ui;max-width:600px;margin:60px auto;padding:0 20px">
<h2>Connected to {team_name}</h2>
<p>Set <code>SLACK_BOT_TOKEN={bot_token}</code> in your env and redeploy.</p>
</body></html>""")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
