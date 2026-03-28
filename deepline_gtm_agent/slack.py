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


# ---------------------------------------------------------------------------
# Markdown → Slack mrkdwn converter
# ---------------------------------------------------------------------------

import re as _re


def md_to_slack(text: str) -> str:
    """
    Convert common Markdown patterns to Slack mrkdwn.
    The LLM is prompted to output mrkdwn directly, but this acts as a safety net.
    """
    # Headers: ### Title → *Title*
    text = _re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=_re.MULTILINE)
    # Bold: **text** → *text*
    text = _re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Italic: _text_ already correct; *text* → _text_ only when not already bold
    # (skip — single * is already Slack bold, leave it)
    # Strikethrough: ~~text~~ → ~text~
    text = _re.sub(r"~~(.+?)~~", r"~\1~", text)
    # Horizontal rules: --- or *** → blank line
    text = _re.sub(r"^[-*]{3,}\s*$", "", text, flags=_re.MULTILINE)
    # Unordered list bullets: "- item" or "* item" → "• item"
    text = _re.sub(r"^[ \t]*[-*]\s+", "• ", text, flags=_re.MULTILINE)
    # Inline links: [text](url) → text (url) — Slack auto-links URLs
    text = _re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return text

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")

# Per-workspace bot tokens — populated at runtime via the OAuth redirect.
# Key: team_id (e.g. "T012AB3CD") → xoxb- bot token for that workspace.
# Falls back to SLACK_BOT_TOKEN for workspaces not yet registered here.
_workspace_tokens: dict[str, str] = {}


def register_workspace_token(team_id: str, bot_token: str) -> None:
    """Store a bot token for a workspace. Called after OAuth install."""
    _workspace_tokens[team_id] = bot_token
    logger.info("Registered token for workspace %s", team_id)


def get_token_for_team(team_id: str) -> str:
    """Return the bot token for the given workspace, falling back to env var."""
    return _workspace_tokens.get(team_id, SLACK_BOT_TOKEN)


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


async def post_message(
    channel: str,
    text: str,
    token: str,
    thread_ts: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Post a message to a Slack channel or thread.

    If posting fails with channel_not_found (bot not in channel) and a user_id
    is provided, falls back to opening a DM with the user.
    """
    payload: dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10,
        )
    data = resp.json()
    if not data.get("ok"):
        error = data.get("error", "")
        logger.error("chat.postMessage failed: %s", error)
        if error == "channel_not_found" and user_id:
            logger.info("Falling back to DM for user %s", user_id)
            async with httpx.AsyncClient() as client:
                dm_resp = await client.post(
                    "https://slack.com/api/conversations.open",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"users": user_id},
                    timeout=10,
                )
            dm_channel = dm_resp.json().get("channel", {}).get("id")
            if dm_channel:
                async with httpx.AsyncClient() as client:
                    fallback = await client.post(
                        "https://slack.com/api/chat.postMessage",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"channel": dm_channel, "text": text},
                        timeout=10,
                    )
                return fallback.json()
    return data


async def add_reaction(channel: str, ts: str, emoji: str, token: str) -> None:
    """Add an emoji reaction to a message. Never raises — failures are logged and ignored."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://slack.com/api/reactions.add",
                headers={"Authorization": f"Bearer {token}"},
                json={"channel": channel, "timestamp": ts, "name": emoji},
                timeout=10,
            )
        data = resp.json()
        if not data.get("ok") and data.get("error") != "already_reacted":
            logger.debug("reactions.add failed: %s", data.get("error"))
    except Exception as e:
        logger.debug("reactions.add error: %s", e)


async def remove_reaction(channel: str, ts: str, emoji: str, token: str) -> None:
    """Remove an emoji reaction from a message. Never raises — failures are logged and ignored."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://slack.com/api/reactions.remove",
                headers={"Authorization": f"Bearer {token}"},
                json={"channel": channel, "timestamp": ts, "name": emoji},
                timeout=10,
            )
        data = resp.json()
        if not data.get("ok") and data.get("error") != "no_reaction":
            logger.debug("reactions.remove failed: %s", data.get("error"))
    except Exception as e:
        logger.debug("reactions.remove error: %s", e)


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

    logger.info("Slack event received: type=%s event_id=%s", event_type, event_id)

    # Dedup
    if event_id and event_id in _seen_event_ids:
        logger.info("Skipping duplicate event: %s", event_id)
        return
    if event_id:
        _seen_event_ids.add(event_id)
        # Keep set bounded
        if len(_seen_event_ids) > 10_000:
            _seen_event_ids.clear()

    # Only handle user messages (ignore bot messages, including our own)
    if event.get("bot_id") or event.get("subtype"):
        logger.info("Ignoring bot/subtype message (bot_id=%s, subtype=%s)", event.get("bot_id"), event.get("subtype"))
        return

    user_text = _extract_text(event)
    if not user_text:
        logger.info("Empty text after extraction, ignoring")
        return

    team_id = payload.get("team_id", "")
    token = get_token_for_team(team_id)

    channel = event.get("channel", "")
    user_id = event.get("user", "")
    logger.info("Processing message team=%s channel=%s text=%.80r", team_id, channel, user_text)
    message_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts") or message_ts

    thread_key = (team_id, channel, thread_ts)

    # Add user message to history
    _conversation_history[thread_key].append({"role": "user", "content": user_text})

    # React with 👀 so the user knows their message is being processed
    if message_ts:
        await add_reaction(channel, message_ts, "eyes", token=token)

    try:
        messages = list(_conversation_history[thread_key])
        reply = await agent_fn(messages)

        if message_ts:
            await remove_reaction(channel, message_ts, "eyes", token=token)
        await post_message(channel, md_to_slack(reply), token=token, thread_ts=thread_ts, user_id=user_id)

        _conversation_history[thread_key].append({"role": "assistant", "content": reply})

        if len(_conversation_history[thread_key]) > 40:
            _conversation_history[thread_key] = _conversation_history[thread_key][-40:]

    except Exception as e:
        error_text = f":warning: Something went wrong: {e}"
        logger.exception("Error processing Slack event")
        if message_ts:
            await remove_reaction(channel, message_ts, "eyes", token=token)
        await post_message(channel, error_text, token=token, thread_ts=thread_ts, user_id=user_id)
