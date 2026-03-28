"""
FastAPI server — Deepline GTM Agent

Endpoints:
  GET  /health          — health check
  POST /chat            — single-turn chat, full response
  POST /chat/stream     — streaming SSE
  POST /slack/events    — Slack Events API webhook (DMs + @mentions)
"""

import json
import logging
import os
from typing import AsyncIterator

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from deepline_gtm_agent import create_gtm_agent
from deepline_gtm_agent.skills import load_skill_docs
from deepline_gtm_agent.dynamic_tools import load_tool_catalog
from deepline_gtm_agent.redis_client import make_checkpointer
import httpx

from deepline_gtm_agent.slack import (
    handle_slack_event,
    verify_slack_signature,
    register_workspace_token,
    SLACK_BOT_TOKEN,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional API key protection for /chat endpoints.
# Set API_KEY env var to enable. Leave unset to run open (e.g. local dev).
_API_KEY = os.environ.get("API_KEY", "")
_bearer = HTTPBearer(auto_error=False)


async def require_api_key(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    if _API_KEY and (not credentials or credentials.credentials != _API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

app = FastAPI(title="Deepline GTM Agent", version="0.1.0")

# CORS: defaults to open for local dev.
# Set CORS_ORIGINS="https://your-app.com,https://other.com" in production.
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Agent singleton — built once at startup with live skill docs
# ---------------------------------------------------------------------------

_agent = None
_skill_docs: str = ""
_tool_catalog: list[dict] = []
_checkpointer = None


@app.on_event("startup")
async def startup():
    """
    Fetch Deepline skill docs + tool catalog at startup.
    Also initialises the Redis checkpointer for persistent conversation memory.
    """
    global _skill_docs, _tool_catalog, _agent, _checkpointer
    import asyncio

    logger.info("Loading Deepline skill docs, tool catalog, and checkpointer...")

    # Load skill docs (async HTTP) and tool catalog (sync subprocess) concurrently
    skill_task = asyncio.create_task(load_skill_docs())
    loop = asyncio.get_event_loop()
    catalog_task = loop.run_in_executor(None, load_tool_catalog)
    _skill_docs, _tool_catalog = await asyncio.gather(skill_task, catalog_task)

    doc_count = _skill_docs.count("## Skill doc:")
    logger.info(
        "Loaded %d skill docs (%.1f KB) and %d tools in catalog",
        doc_count, len(_skill_docs) / 1024, len(_tool_catalog),
    )

    # Init LangGraph checkpointer (Redis if REDIS_URL set, else MemorySaver)
    _checkpointer = make_checkpointer()
    # AsyncRedisSaver requires explicit setup
    if _checkpointer is not None:
        try:
            await _checkpointer.__aenter__()
        except Exception:
            pass  # MemorySaver doesn't need setup; AsyncRedisSaver does

    model = os.environ.get("LLM_MODEL", "anthropic:claude-opus-4-6")
    _agent = create_gtm_agent(
        model=model,
        skill_docs=_skill_docs or None,
        tool_catalog=_tool_catalog or None,
        checkpointer=_checkpointer,
    )
    logger.info(
        "Agent ready (model=%s, skills=%s, tools=%d, memory=%s)",
        model,
        "loaded" if _skill_docs else "unavailable",
        len(_tool_catalog),
        type(_checkpointer).__name__ if _checkpointer else "none",
    )


def get_agent():
    global _agent
    if _agent is None:
        model = os.environ.get("LLM_MODEL", "anthropic:claude-opus-4-6")
        _agent = create_gtm_agent(
            model=model,
            skill_docs=_skill_docs or None,
            tool_catalog=_tool_catalog or None,
            checkpointer=_checkpointer,
        )
    return _agent


async def run_agent(messages: list[dict], thread_id: str | None = None) -> str:
    """Run the GTM agent and return a plain text reply.

    thread_id: when provided, the LangGraph checkpointer persists state across
    calls with the same thread_id — enabling true multi-turn memory.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}} if thread_id else {}
    result = await agent.ainvoke({"messages": messages}, config=config or None)
    last = result["messages"][-1]
    content = last.content
    if isinstance(content, list):
        return "".join(
            block["text"] if isinstance(block, dict) else str(block)
            for block in content
            if not isinstance(block, dict) or block.get("type") == "text"
        )
    return str(content)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    thread_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    thread_id: str | None = None


# ---------------------------------------------------------------------------
# HTTP chat endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent": "deepline-gtm-agent",
        "slack": "configured" if SLACK_BOT_TOKEN else "not configured",
        "skills": f"{_skill_docs.count('## Skill doc:')} docs loaded" if _skill_docs else "not loaded",
        "tools": f"{len(_tool_catalog)} Deepline tools registered" if _tool_catalog else "catalog not loaded",
    }


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    try:
        reply = await run_agent(messages, thread_id=req.thread_id)
        return ChatResponse(message=reply, thread_id=req.thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream", dependencies=[Depends(require_api_key)])
async def chat_stream(req: ChatRequest):
    agent = get_agent()
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    config = {}
    if req.thread_id:
        config["configurable"] = {"thread_id": req.thread_id}

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in agent.astream(
                {"messages": messages},
                config=config or None,
                stream_mode="messages",
            ):
                if isinstance(chunk, tuple):
                    msg, _ = chunk
                    if hasattr(msg, "content") and msg.content:
                        content = msg.content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    yield f"data: {json.dumps({'token': block['text']})}\n\n"
                        else:
                            yield f"data: {json.dumps({'token': str(content)})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Slack Events API
# ---------------------------------------------------------------------------


@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Slack Events API webhook.

    Handles:
      - url_verification challenge (sent once during app setup)
      - app_mention  — bot @-mentioned in a channel
      - message.im   — DM sent directly to the bot

    Security: verifies X-Slack-Signature on every request.
    Responds with 200 immediately; runs agent in background to beat Slack's 3s timeout.
    """
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400, content="Bad JSON")

    # ── URL verification (one-time during app setup) ──────────────────────
    # Respond before signature check — the challenge handshake IS the verification.
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body, timestamp, signature):
        logger.warning("Slack signature verification failed")
        return Response(status_code=403, content="Invalid signature")

    # ── Event callback ────────────────────────────────────────────────────
    if payload.get("type") == "event_callback":
        event_type = payload.get("event", {}).get("type", "")

        event = payload.get("event", {})
        channel_type = event.get("channel_type", "")
        # app_mention  → @mention in a channel
        # message + im → DM to the bot
        # Skip plain "message" events in channels — they duplicate app_mention
        if event_type == "app_mention" or (event_type == "message" and channel_type == "im"):
            background_tasks.add_task(handle_slack_event, payload, run_agent)

    # Always return 200 so Slack doesn't retry
    return Response(status_code=200)


@app.get("/slack/oauth_redirect")
async def slack_oauth_redirect(code: str = None, error: str = None):
    """
    Slack OAuth redirect handler.

    Slack sends the user here after they install the app. This endpoint exchanges
    the short-lived code for a bot token using SLACK_CLIENT_ID + SLACK_CLIENT_SECRET.

    Required env vars: SLACK_CLIENT_ID, SLACK_CLIENT_SECRET
    """
    if error:
        return HTMLResponse(f"<h2>OAuth error</h2><p>{error}</p>", status_code=400)

    if not code:
        return HTMLResponse("<h2>Missing code</h2><p>No OAuth code in request.</p>", status_code=400)

    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return HTMLResponse(
            "<h2>Not configured</h2>"
            "<p>Set <code>SLACK_CLIENT_ID</code> and <code>SLACK_CLIENT_SECRET</code> env vars, then reinstall the app.</p>",
            status_code=500,
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={"client_id": client_id, "client_secret": client_secret, "code": code},
            timeout=10,
        )

    data = resp.json()
    if not data.get("ok"):
        return HTMLResponse(
            f"<h2>OAuth failed</h2><p>{data.get('error', 'unknown error')}</p>",
            status_code=400,
        )

    bot_token = data.get("access_token", "")
    team_id = data.get("team", {}).get("id", "")
    team = data.get("team", {}).get("name", "your workspace")

    # Register this token so the bot responds in the right workspace immediately
    if team_id and bot_token:
        register_workspace_token(team_id, bot_token)

    logger.info("Slack OAuth success for workspace: %s (%s)", team, team_id)

    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><title>Deepline GTM Agent — Slack Connected</title>
<style>body{{font-family:system-ui,sans-serif;max-width:600px;margin:60px auto;padding:0 20px;}}
code{{background:#f4f4f4;padding:4px 8px;border-radius:4px;font-size:14px;word-break:break-all;}}</style>
</head><body>
<h2>✅ Slack connected — {team}</h2>
<p>Set this as your <code>SLACK_BOT_TOKEN</code> environment variable in Railway:</p>
<pre><code>{bot_token}</code></pre>
<p>Then redeploy. The bot will be live once the deploy completes.</p>
</body></html>""")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
