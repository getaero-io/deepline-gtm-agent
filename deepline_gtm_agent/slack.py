"""
Slack bot integration for the Deepline GTM Agent.

Handles:
- Slack URL verification challenge (required during app setup)
- Signature verification on every request (HMAC-SHA256)
- app_mention events (someone @-mentions the bot in a channel)
- message.im events (DM to the bot)
- Threading: replies in the same Slack thread, maintains conversation history
- Async processing: returns 200 immediately, processes in background to beat 3s timeout

Required env vars:
  SLACK_BOT_TOKEN      — xoxb-... from OAuth & Permissions
  SLACK_SIGNING_SECRET — from Basic Information > App Credentials
"""

import hashlib
import hmac
import json
import logging
import os
import time
from collections import defaultdict
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")

# In-memory conversation history per Slack thread.
# Key: (channel, thread_ts) → list of {"role": ..., "content": ...}
# Resets on process restart — good enough for demo, swap for Redis in prod.
_conversation_history: dict[tuple, list] = defaultdict(list)

# Dedup cache: Slack sometimes sends events twice. Track processed event IDs.
_seen_event_ids: set[str] = set()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify a Slack request signature using HMAC-SHA256.
    Rejects requests older than 5 minutes to prevent replay attacks.
    """
    if not SLACK_SIGNING_SECRET:
        logger.warning("SLACK_SIGNING_SECRET not set — skipping signature check")
        return True

    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - ts) > 300:
        logger.warning("Slack request timestamp too old: %s", timestamp)
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode()
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring,
        hashlib.sha256,
    ).hexdigest()  # type: ignore[attr-defined]

    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Slack API calls
# ---------------------------------------------------------------------------


async def post_message(channel: str, text: str, thread_ts: str | None = None) -> dict:
    """Post a message to a Slack channel or thread."""
    payload: dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json=payload,
            timeout=10,
        )
    data = resp.json()
    if not data.get("ok"):
        logger.error("chat.postMessage failed: %s", data.get("error"))
    return data


async def update_message(channel: str, ts: str, text: str) -> dict:
    """Update an existing Slack message (used to swap 'Thinking...' with real reply)."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.update",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json={"channel": channel, "ts": ts, "text": text},
            timeout=10,
        )
    return resp.json()


async def get_bot_user_id() -> str:
    """Fetch the bot's own user ID (used to filter out self-messages)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            timeout=10,
        )
    return resp.json().get("user_id", "")


# ---------------------------------------------------------------------------
# Event processing
# ---------------------------------------------------------------------------


def _extract_text(event: dict) -> str:
    """Strip bot mention prefix from message text."""
    text = event.get("text", "").strip()
    # Remove <@BOTID> mention prefix if present
    if text.startswith("<@"):
        text = text.split(">", 1)[-1].strip()
    return text


async def handle_slack_event(payload: dict, agent_fn) -> None:
    """
    Process a single Slack event asynchronously.
    Called as a background task — Slack has already received its 200.

    agent_fn: async callable that takes a list of messages and returns a reply string.
    """
    event = payload.get("event", {})
    event_type = event.get("type", "")
    event_id = payload.get("event_id", "")

    # Dedup
    if event_id and event_id in _seen_event_ids:
        return
    if event_id:
        _seen_event_ids.add(event_id)
        # Keep set bounded
        if len(_seen_event_ids) > 10_000:
            _seen_event_ids.clear()

    # Only handle user messages (ignore bot messages, including our own)
    if event.get("bot_id") or event.get("subtype"):
        return

    user_text = _extract_text(event)
    if not user_text:
        return

    channel = event.get("channel", "")
    # Use thread_ts if this is a reply; otherwise start a new thread from message ts
    thread_ts = event.get("thread_ts") or event.get("ts")

    thread_key = (channel, thread_ts)

    # Add user message to history
    _conversation_history[thread_key].append({"role": "user", "content": user_text})

    # Post a "Thinking..." placeholder immediately so the user sees activity
    thinking_resp = await post_message(channel, "_Thinking…_", thread_ts=thread_ts)
    thinking_ts = thinking_resp.get("ts")

    try:
        messages = list(_conversation_history[thread_key])
        reply = await agent_fn(messages)

        # Update placeholder with real reply
        if thinking_ts:
            await update_message(channel, thinking_ts, reply)
        else:
            await post_message(channel, reply, thread_ts=thread_ts)

        # Store assistant reply in history
        _conversation_history[thread_key].append({"role": "assistant", "content": reply})

        # Trim history to last 20 turns to avoid token bloat
        if len(_conversation_history[thread_key]) > 40:
            _conversation_history[thread_key] = _conversation_history[thread_key][-40:]

    except Exception as e:
        error_text = f"Something went wrong: {e}"
        logger.exception("Error processing Slack event")
        if thinking_ts:
            await update_message(channel, thinking_ts, error_text)
        else:
            await post_message(channel, error_text, thread_ts=thread_ts)
