"""
Redis client — lazy async connection with graceful in-memory fallback.

If REDIS_URL is set (Railway provides it automatically when you add a Redis plugin),
all conversation history and LangGraph checkpointer state is persisted in Redis.

If REDIS_URL is not set, everything falls back to in-memory dicts — fine for local
dev but state is lost on process restart.
"""

import json
import logging
import os
from collections import defaultdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "")

# ---------------------------------------------------------------------------
# Async Redis client (redis-py ≥ 5 has built-in async support)
# ---------------------------------------------------------------------------

_redis: Any = None  # redis.asyncio.Redis or None


async def get_redis():
    """Return a live async Redis client, or None if Redis is not configured."""
    global _redis
    if _redis is not None:
        return _redis
    if not REDIS_URL:
        return None
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connected: %s", REDIS_URL.split("@")[-1])  # hide credentials
    except Exception as e:
        logger.warning("Redis connection failed — falling back to in-memory: %s", e)
        _redis = None
    return _redis


# ---------------------------------------------------------------------------
# Conversation history helpers (used by slack.py)
# ---------------------------------------------------------------------------

# In-memory fallback store: key → list[dict]
_memory_store: dict[str, list] = defaultdict(list)

HISTORY_TTL = 7 * 24 * 3600  # 7 days


async def get_history(key: str) -> list[dict]:
    """Load conversation history for a key."""
    r = await get_redis()
    if r:
        try:
            raw = await r.get(key)
            return json.loads(raw) if raw else []
        except Exception as e:
            logger.warning("Redis get_history failed: %s", e)
    return list(_memory_store.get(key, []))


async def save_history(key: str, messages: list[dict]) -> None:
    """Persist conversation history for a key (replaces entirely)."""
    r = await get_redis()
    if r:
        try:
            await r.set(key, json.dumps(messages), ex=HISTORY_TTL)
            return
        except Exception as e:
            logger.warning("Redis save_history failed: %s", e)
    _memory_store[key] = list(messages)


async def append_history(key: str, message: dict, max_messages: int = 40) -> list[dict]:
    """Append a message to history and return the updated list."""
    messages = await get_history(key)
    messages.append(message)
    if len(messages) > max_messages:
        messages = messages[-max_messages:]
    await save_history(key, messages)
    return messages


# ---------------------------------------------------------------------------
# LangGraph Redis checkpointer factory
# ---------------------------------------------------------------------------


def make_checkpointer():
    """
    Return a LangGraph Redis checkpointer if Redis is configured, else None.

    Uses langgraph-checkpoint-redis (AsyncRedisSaver).
    Falls back gracefully to MemorySaver when Redis is unavailable.
    """
    if not REDIS_URL:
        logger.info("No REDIS_URL — using LangGraph MemorySaver (in-memory, not persistent)")
        try:
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()
        except ImportError:
            return None

    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        checkpointer = AsyncRedisSaver.from_conn_string(REDIS_URL)
        logger.info("LangGraph checkpointer: AsyncRedisSaver (Redis)")
        return checkpointer
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-redis not installed — install it or add to deps. "
            "Falling back to MemorySaver."
        )
    except Exception as e:
        logger.warning("Redis checkpointer init failed: %s — using MemorySaver", e)

    try:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    except ImportError:
        return None
