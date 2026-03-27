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

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deepline_gtm_agent import create_gtm_agent
from deepline_gtm_agent.skills import load_skill_docs
from deepline_gtm_agent.slack import (
    handle_slack_event,
    verify_slack_signature,
    SLACK_BOT_TOKEN,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Deepline GTM Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Agent singleton — built once at startup with live skill docs
# ---------------------------------------------------------------------------

_agent = None
_skill_docs: str = ""


@app.on_event("startup")
async def startup():
    """Fetch Deepline skill docs at startup so the agent has full provider guidance."""
    global _skill_docs, _agent
    logger.info("Fetching Deepline skill docs...")
    _skill_docs = await load_skill_docs()
    doc_count = _skill_docs.count("## Skill doc:")
    logger.info("Loaded %d skill docs (%.1f KB)", doc_count, len(_skill_docs) / 1024)
    # Pre-build the agent so first request isn't slow
    model = os.environ.get("LLM_MODEL", "anthropic:claude-opus-4-6")
    _agent = create_gtm_agent(model=model, skill_docs=_skill_docs or None)
    logger.info("Agent ready (model=%s, skills=%s)", model, "loaded" if _skill_docs else "unavailable")


def get_agent():
    global _agent
    if _agent is None:
        model = os.environ.get("LLM_MODEL", "anthropic:claude-opus-4-6")
        _agent = create_gtm_agent(model=model, skill_docs=_skill_docs or None)
    return _agent


async def run_agent(messages: list[dict]) -> str:
    """Run the GTM agent and return a plain text reply."""
    agent = get_agent()
    result = await agent.ainvoke({"messages": messages})
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
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    try:
        reply = await run_agent(messages)
        return ChatResponse(message=reply, thread_id=req.thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
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
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body, timestamp, signature):
        logger.warning("Slack signature verification failed")
        return Response(status_code=403, content="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400, content="Bad JSON")

    # ── URL verification (one-time during app setup) ──────────────────────
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    # ── Event callback ────────────────────────────────────────────────────
    if payload.get("type") == "event_callback":
        event_type = payload.get("event", {}).get("type", "")

        if event_type in ("app_mention", "message"):
            # Kick off async processing — return 200 to Slack immediately
            background_tasks.add_task(handle_slack_event, payload, run_agent)

    # Always return 200 so Slack doesn't retry
    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
