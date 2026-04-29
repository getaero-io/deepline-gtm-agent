"""
Thin wrapper around the Deepline API for executing provider operations.

Two backends:
  1. HTTP API (preferred when DEEPLINE_API_KEY is set) — faster, no subprocess
  2. CLI subprocess fallback (for local dev where CLI is authenticated)
"""

import json
import logging
import os
import subprocess
from typing import Any

from deepline_gtm_agent.cost_optimization import truncate_tool_result, short_error_stack

logger = logging.getLogger(__name__)

DEEPLINE_API_BASE = os.environ.get("DEEPLINE_API_BASE_URL", "https://code.deepline.com")
TIMEOUT_SECONDS = 120
MAX_RETRIES = 2


def deepline_execute(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a Deepline tool operation and return the parsed result.

    Prefers HTTP API when DEEPLINE_API_KEY is set; falls back to CLI subprocess.
    Includes retry logic for transient failures and truncates large results.
    """
    api_key = os.environ.get("DEEPLINE_API_KEY")

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            if api_key:
                result = _execute_http(operation, payload, api_key)
            else:
                result = _execute_cli(operation, payload)
            return truncate_tool_result(result)
        except Exception as e:
            last_error = e
            err_str = str(e)
            # Don't retry on auth/validation errors
            if "401" in err_str or "403" in err_str or "CREDENTIALS_MISSING" in err_str:
                raise
            if "400" in err_str or "validation" in err_str.lower():
                raise
            # Retry on transient errors (429, 5xx, network)
            if attempt < MAX_RETRIES - 1:
                import time
                wait = 2 ** attempt
                logger.warning("Retrying %s in %ds (attempt %d): %s", operation, wait, attempt + 1, err_str[:100])
                time.sleep(wait)

    raise last_error


def _execute_http(operation: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Call the Deepline REST API directly."""
    try:
        import httpx
    except ImportError:
        import urllib.request, urllib.error
        return _execute_http_stdlib(operation, payload, api_key)

    # Parse provider + operation name  (e.g. "apollo_search_people" → provider="apollo", op="search_people")
    # The API uses provider-prefixed operation IDs in the execute endpoint
    url = f"{DEEPLINE_API_BASE}/api/v2/integrations/{operation}/execute"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"payload": payload}

    with httpx.Client(timeout=120) as client:
        response = client.post(url, json=body, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(
            f"deepline execute failed ({operation}): {response.text[:300]}"
        )

    data = response.json()
    # Unwrap result envelope if present
    if "result" in data and "data" in data.get("result", {}):
        return data["result"]["data"]
    return data


def _execute_http_stdlib(operation: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    """HTTP call using stdlib urllib (no httpx dependency)."""
    import urllib.request, urllib.error

    url = f"{DEEPLINE_API_BASE}/api/v2/integrations/{operation}/execute"
    body = json.dumps({"payload": payload}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"deepline execute failed ({operation}): {e.read().decode()[:300]}")

    if "result" in data and "data" in data.get("result", {}):
        return data["result"]["data"]
    return data


def _execute_cli(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Fall back to CLI subprocess when no API key is set (local dev).
    Uses --payload-output-format json to get structured output.
    """
    cmd = [
        "deepline", "tools", "execute", operation,
        "--payload", json.dumps(payload),
        "--payload-output-format", "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"deepline execute failed ({operation}): {result.stderr.strip() or result.stdout.strip()}"
        )

    # stdout is a file path to the JSON output
    json_path = result.stdout.strip()
    if json_path and os.path.exists(json_path):
        with open(json_path) as f:
            data = json.load(f)
        if "result" in data and "data" in data.get("result", {}):
            return data["result"]["data"]
        return data

    raise RuntimeError(f"deepline execute: unexpected output for {operation}: {result.stdout[:200]}")
