"""FastAPI broker for Deepline GTM native v2 chat.

The broker keeps transport concerns here: REST, web chat, Slack verification,
Slack formatting, and optional bearer auth. Deepline owns the agent runtime,
tool execution, provider credentials, billing, and streaming contract.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))
from deepline_gtm_agent.formatting import md_to_slack, truncate_for_slack
from deepline_gtm_agent.v2_client import DeeplineV2Client, extract_text_from_stream_chunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("API_KEY", "")
_bearer = HTTPBearer(auto_error=False)


async def require_api_key(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    if _API_KEY and (not credentials or credentials.credentials != _API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_deepline_client() -> DeeplineV2Client:
    return DeeplineV2Client()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Deepline GTM native v2 broker starting")
    yield


app = FastAPI(title="Deepline GTM Native Agent", version="2.0.0", lifespan=lifespan)

_cors_raw = os.environ.get("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_raw.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    messages: list[ChatMessage] | None = None
    thread_id: str | None = None
    enabled_tool_ids: list[str] | None = Field(default=None, alias="enabledToolIds")
    max_tool_calls: int | None = Field(default=None, alias="maxToolCalls")
    model: str | None = None

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    reply: str
    thread_id: str | None = None


BULK_PROSPECT_LIST_INSTRUCTIONS = """\
Bulk prospect/list requests must use Deepline's native v2 list-building workflow.
Create an execution plan, produce or reference an auditable seed list, and run only
a pilot/sample first unless the user has explicitly approved the full run. Do not
invent prospects, companies, emails, LinkedIn URLs, or CSV rows. If a CSV/artifact
is requested, return the artifact/status details Deepline produced and the next
approval step before any full enrichment.
"""

_BULK_LIST_TERMS = ("csv", "list", "prospect", "prospects", "contacts", "accounts")
_BULK_ACTION_TERMS = ("build", "create", "find", "source", "generate")
_BULK_COUNT_TERMS = ("5", "10", "20", "25", "50", "100", "bulk", "batch")


def _looks_like_bulk_prospect_list(message: str) -> bool:
    text = message.lower()
    return (
        any(term in text for term in _BULK_LIST_TERMS)
        and any(term in text for term in _BULK_ACTION_TERMS)
        and any(term in text for term in _BULK_COUNT_TERMS)
    )


def _with_bulk_prospecting_guidance(message: str) -> str:
    if not _looks_like_bulk_prospect_list(message):
        return message
    if "native v2 list-building workflow" in message:
        return message
    return f"{BULK_PROSPECT_LIST_INSTRUCTIONS}\n\nUser request:\n{message}"


def _chat_payload(req: ChatRequest) -> dict[str, Any]:
    prompt = _with_bulk_prospecting_guidance(req.message)
    messages = (
        [{"role": m.role, "content": m.content} for m in req.messages]
        if req.messages and prompt == req.message
        else [{"role": "user", "content": prompt}]
    )
    payload: dict[str, Any] = {
        "prompt": prompt,
        "messages": messages,
        "response_mode": "stream",
    }
    if req.enabled_tool_ids is not None:
        payload["enabledToolIds"] = req.enabled_tool_ids
    if req.max_tool_calls is not None:
        payload["maxToolCalls"] = req.max_tool_calls
    if req.model:
        payload["model"] = req.model
    return payload


async def _collect_native_reply(payload: dict[str, Any]) -> str:
    client = get_deepline_client()
    parts: list[str] = []
    async for chunk in client.stream_agent(payload):
        parts.append(extract_text_from_stream_chunk(chunk))
    return "".join(parts).strip()


@app.get("/health")
async def health():
    body = {
        "status": "ok" if os.environ.get("DEEPLINE_API_KEY") else "needs setup",
        "agent": "deepline-gtm-native-v2",
        "deepline": "configured" if os.environ.get("DEEPLINE_API_KEY") else "missing DEEPLINE_API_KEY",
        "host": os.environ.get("DEEPLINE_HOST_URL") or os.environ.get("DEEPLINE_API_BASE_URL") or "https://code.deepline.com",
        "slack": "configured" if os.environ.get("SLACK_BOT_TOKEN") else "not configured",
    }
    return JSONResponse(body, status_code=200 if os.environ.get("DEEPLINE_API_KEY") else 503)


@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    html_path = Path(__file__).parent / "chat.html"
    if html_path.exists():
        return html_path.read_text()
    return "<h2>Deepline GTM Agent</h2><p>POST to /chat or /chat/stream</p>"


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    reply = await _collect_native_reply(_chat_payload(req))
    return ChatResponse(reply=reply, thread_id=req.thread_id)


@app.post("/chat/stream", dependencies=[Depends(require_api_key)])
async def chat_stream(req: ChatRequest):
    payload = _chat_payload(req)

    async def generate() -> AsyncIterator[str]:
        async for chunk in get_deepline_client().stream_agent(payload):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
_workspace_tokens: dict[str, str] = {}


def _verify_slack_sig(body: bytes, timestamp: str, signature: str) -> bool:
    if not SLACK_SIGNING_SECRET:
        return False
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
        for msg in data.get("messages", [])[:-1]:
            text = msg.get("text", "").strip()
            if text.startswith("<@"):
                text = text.split(">", 1)[-1].strip()
            if not text:
                continue
            messages.append({"role": "assistant" if msg.get("bot_id") else "user", "content": text})
        return messages
    except Exception as e:
        logger.warning("Failed to fetch Slack thread history: %s", e)
        return []


async def _handle_slack_event(event: dict, team_id: str):
    token = _workspace_tokens.get(team_id, SLACK_BOT_TOKEN)
    channel = event.get("channel", "")
    user_text = event.get("text", "").strip()
    if user_text.startswith("<@"):
        user_text = user_text.split(">", 1)[-1].strip()
    if not user_text:
        return

    message_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts") or message_ts
    await _slack_react(channel, message_ts, "eyes", token)

    try:
        history = await _fetch_thread_history(channel, thread_ts, token) if event.get("thread_ts") else []
        messages = history + [{"role": "user", "content": user_text}]
        reply = await _collect_native_reply(
            {
                "prompt": user_text,
                "messages": messages,
                "response_mode": "stream",
            }
        )

        await _slack_react(channel, message_ts, "eyes", token, remove=True)
        slack_reply = md_to_slack(reply) if reply else "(no response)"
        for chunk in truncate_for_slack(slack_reply):
            await _slack_post(channel, chunk, token, thread_ts)
    except Exception as e:
        logger.exception("Slack handler error")
        try:
            await _slack_react(channel, message_ts, "eyes", token, remove=True)
            await _slack_post(channel, f":warning: Error: {e}", token, thread_ts)
        except Exception:
            logger.exception("Failed to send Slack error message")


_seen_events: OrderedDict[str, None] = OrderedDict()
_MAX_SEEN = 5000


def _mark_seen(event_id: str) -> bool:
    if event_id in _seen_events:
        return True
    _seen_events[event_id] = None
    while len(_seen_events) > _MAX_SEEN:
        _seen_events.popitem(last=False)
    return False


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

        if event_id and _mark_seen(event_id):
            return Response(status_code=200)
        if event.get("bot_id") or event.get("subtype"):
            return Response(status_code=200)
        if etype == "app_mention" or (etype == "message" and ctype == "im"):
            background_tasks.add_task(_handle_slack_event, event, payload.get("team_id", ""))

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
