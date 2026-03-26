"""
FastAPI server that exposes the GTM agent as a streaming HTTP endpoint.

POST /chat           — single-turn chat, returns full response
POST /chat/stream    — streaming SSE response
GET  /health         — health check
"""

import json
import os
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deepline_gtm_agent import create_gtm_agent

app = FastAPI(title="Deepline GTM Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build agent once at startup
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        model = os.environ.get("LLM_MODEL", "anthropic:claude-opus-4-6")
        _agent = create_gtm_agent(model=model)
    return _agent


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    thread_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    thread_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "deepline-gtm-agent"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Single-turn chat — waits for full response before returning."""
    agent = get_agent()
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    config = {}
    if req.thread_id:
        config["configurable"] = {"thread_id": req.thread_id}

    try:
        result = await agent.ainvoke({"messages": messages}, config=config or None)
        reply = result["messages"][-1].content
        return ChatResponse(message=reply, thread_id=req.thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming SSE endpoint — yields tokens as they arrive."""
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
                # chunk is (message, metadata) tuple in messages stream mode
                if isinstance(chunk, tuple):
                    msg, meta = chunk
                    if hasattr(msg, "content") and msg.content:
                        content = msg.content
                        if isinstance(content, list):
                            # Multi-part content block
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    data = json.dumps({"token": block["text"]})
                                    yield f"data: {data}\n\n"
                        else:
                            data = json.dumps({"token": str(content)})
                            yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
