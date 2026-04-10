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

    await _slack_react(channel, message_ts, "eyes", token)

    try:
        client = get_client()
        loop = asyncio.get_event_loop()

        session_id = await loop.run_in_executor(
            None, create_session, client, f"Slack: {user_text[:50]}"
        )
        prompt = f"{BOOTSTRAP_MSG}\n\nThen: {user_text}"
        await loop.run_in_executor(None, send_message, client, session_id, prompt)

        def _collect():
            parts = []
            for evt in stream_events(client, session_id):
                if evt["type"] == "text":
                    parts.append(evt["text"])
            return "".join(parts)

        reply = await loop.run_in_executor(None, _collect)

        await _slack_react(channel, message_ts, "eyes", token, remove=True)
        await _slack_post(channel, reply or "(no response)", token, thread_ts)
    except Exception as e:
        logger.exception("Slack handler error")
        await _slack_react(channel, message_ts, "eyes", token, remove=True)
        await _slack_post(channel, f":warning: Error: {e}", token, thread_ts)


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
