"""
Waterfall.io API client.

Async job pattern: POST to launch, GET to poll until status != RUNNING.
Sync endpoints return results inline.
"""
import json
import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

WATERFALL_BASE = "https://api.waterfall.io"
POLL_INTERVAL = 2  # seconds between polls
POLL_MAX_WAIT = 120  # max seconds to wait for async job


def _get_api_key() -> str:
    key = os.environ.get("WATERFALL_API_KEY", "")
    if not key:
        raise RuntimeError("WATERFALL_API_KEY not set. Get your key at waterfall.io")
    return key


def _headers() -> dict:
    return {"x-api-key": _get_api_key(), "Content-Type": "application/json"}


def waterfall_request(method: str, path: str, payload: Optional[dict] = None, params: Optional[dict] = None) -> dict:
    """Make a single request to Waterfall.io API."""
    url = f"{WATERFALL_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        if method == "GET":
            resp = client.get(url, headers=_headers(), params=params)
        else:
            resp = client.post(url, headers=_headers(), json=payload or {})

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "10"))
        raise RuntimeError(f"Waterfall rate limited. Retry after {retry_after}s")
    if resp.status_code == 401:
        raise RuntimeError("Waterfall API key missing. Set WATERFALL_API_KEY env var.")
    if resp.status_code == 403:
        raise RuntimeError("Waterfall API key invalid or insufficient permissions.")
    if resp.status_code != 200:
        raise RuntimeError(f"Waterfall API error ({resp.status_code}): {resp.text[:300]}")

    return resp.json()


def waterfall_async_job(path: str, payload: dict, poll_path: Optional[str] = None) -> dict:
    """Launch an async Waterfall job and poll until complete."""
    result = waterfall_request("POST", path, payload=payload)
    job_id = result.get("job_id")
    if not job_id:
        return result  # Might be a sync endpoint

    get_path = poll_path or path
    elapsed = 0
    while elapsed < POLL_MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        poll_result = waterfall_request("GET", get_path, params={"job_id": job_id})
        status = poll_result.get("status", "")
        if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            return poll_result

    raise RuntimeError(f"Waterfall job {job_id} timed out after {POLL_MAX_WAIT}s")
