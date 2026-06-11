"""Small Deepline v2 API client used by the managed broker.

This intentionally mirrors the public v2 contract instead of reimplementing
provider routing, result unwrapping, or CLI fallback behavior locally.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

DEFAULT_DEEPLINE_BASE_URL = "https://code.deepline.com"
V2_EXECUTE_RESPONSE_CONTRACT = "v2-tool-response"


class DeeplineV2Client:
    """Async client for Deepline's SDK-facing v2 API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        resolved_key = api_key or os.environ.get("DEEPLINE_API_KEY", "")
        if not resolved_key:
            raise RuntimeError("DEEPLINE_API_KEY is required.")
        self.api_key = resolved_key
        self.base_url = (
            base_url
            or os.environ.get("DEEPLINE_HOST_URL")
            or os.environ.get("DEEPLINE_API_BASE_URL")
            or DEFAULT_DEEPLINE_BASE_URL
        ).rstrip("/")
        self._transport = transport
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-deepline-execute-response-contract": V2_EXECUTE_RESPONSE_CONTRACT,
        }

    async def execute_tool(
        self,
        tool_id: str,
        payload: dict[str, Any] | None = None,
        *,
        include_tool_metadata: bool = False,
    ) -> dict[str, Any]:
        """Execute one Deepline tool through `/api/v2/integrations/{toolId}/execute`."""
        headers = self._headers()
        if include_tool_metadata:
            headers["x-deepline-include-tool-metadata"] = "true"
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as http:
            response = await http.post(
                f"/api/v2/integrations/{tool_id}/execute",
                headers=headers,
                json={"payload": payload or {}},
            )
            response.raise_for_status()
            return response.json()

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return Deepline's SDK-facing v2 tool list."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as http:
            response = await http.get("/api/v2/tools", headers=self._headers())
            response.raise_for_status()
            data = response.json()
        tools = data.get("tools", data)
        return tools if isinstance(tools, list) else []

    async def search_tools(self, query: str = "") -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as http:
            response = await http.get(
                "/api/v2/tools/search",
                headers=self._headers(),
                params={"q": query, "search_mode": "v2"},
            )
            response.raise_for_status()
            return response.json()

    async def stream_agent(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        """Yield the native Deepline `deeplineagent` UI-message stream as text chunks."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=None,
            transport=self._transport,
        ) as http:
            async with http.stream(
                "POST",
                "/api/v2/integrations/deeplineagent/stream",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk


def extract_text_from_stream_chunk(chunk: str) -> str:
    """Best-effort text extraction for Deepline/AI SDK SSE chunks.

    Streaming callers should proxy raw chunks. Non-streaming adapters use this
    to collapse common UI-message event shapes into a final text response.
    """
    text_parts: list[str] = []
    for raw_line in chunk.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            for key in ("text", "textDelta", "delta"):
                value = event.get(key)
                if isinstance(value, str):
                    text_parts.append(value)
                    break
            part = event.get("part")
            if isinstance(part, dict):
                value = part.get("text") or part.get("textDelta")
                if isinstance(value, str):
                    text_parts.append(value)
    return "".join(text_parts)
