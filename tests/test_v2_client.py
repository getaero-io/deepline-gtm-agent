import asyncio
import json
from types import SimpleNamespace

import httpx

from deepline_gtm_agent.v2_client import DeeplineV2Client, extract_text_from_stream_chunk
from tests.run_evals import (
    ToolCallCapture,
    _tool_calls_from_native_stream_chunk,
    run_agent_hermes,
    run_agent_http,
)


def test_execute_tool_uses_v2_tool_route():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["headers"] = dict(request.headers)
        seen["json"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "toolResponse": {"raw": {"email": "jane@acme.com"}},
            },
        )

    client = DeeplineV2Client(
        api_key="dl_test",
        base_url="https://code.deepline.com",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.execute_tool("hunter_email_finder", {"domain": "acme.com"}))

    assert seen["path"] == "/api/v2/integrations/hunter_email_finder/execute"
    assert seen["headers"]["authorization"] == "Bearer dl_test"
    assert seen["headers"]["x-deepline-execute-response-contract"] == "v2-tool-response"
    assert result["toolResponse"]["raw"]["email"] == "jane@acme.com"


def test_stream_agent_uses_native_deeplineagent_stream_route():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/integrations/deeplineagent/stream"
        assert request.headers["authorization"] == "Bearer dl_test"
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"type":"text-delta","textDelta":"hello"}\n\n',
        )

    client = DeeplineV2Client(
        api_key="dl_test",
        base_url="https://code.deepline.com",
        transport=httpx.MockTransport(handler),
    )

    async def collect():
        return [chunk async for chunk in client.stream_agent({"prompt": "hi"})]

    chunks = asyncio.run(collect())

    assert chunks == ['data: {"type":"text-delta","textDelta":"hello"}\n\n']


def test_extract_text_from_native_stream_chunks():
    chunk = (
        'data: {"type":"text-delta","textDelta":"hello"}\n\n'
        'data: {"type":"text-delta","delta":" world"}\n\n'
        "data: [DONE]\n\n"
    )

    assert extract_text_from_stream_chunk(chunk) == "hello world"


def test_legacy_deepline_execute_preserves_cli_fallback_without_api_key(monkeypatch):
    import deepline_gtm_agent.deepline as deepline

    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "completed", "toolResponse": {"ok": True}}),
            stderr="",
        )

    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)
    monkeypatch.setattr(deepline.subprocess, "run", fake_run)

    result = deepline.deepline_execute("hunter_email_finder", {"domain": "acme.com"})

    assert seen["cmd"] == [
        "deepline",
        "tools",
        "execute",
        "hunter_email_finder",
        "--input",
        '{"domain": "acme.com"}',
        "--json",
    ]
    assert seen["kwargs"]["capture_output"] is True
    assert result["toolResponse"]["ok"] is True


def test_legacy_deepline_execute_prefers_v2_sdk_with_api_key(monkeypatch):
    import deepline_gtm_agent.deepline as deepline

    class FakeClient:
        def __init__(self, base_url):
            self.base_url = base_url

        async def execute_tool(self, operation, payload, include_tool_metadata=False):
            return {
                "operation": operation,
                "payload": payload,
                "include_tool_metadata": include_tool_metadata,
                "base_url": self.base_url,
            }

    def fail_cli(*args, **kwargs):
        raise AssertionError("DEEPLINE_API_KEY should keep deepline_execute on the v2 SDK path")

    monkeypatch.setenv("DEEPLINE_API_KEY", "dl_test")
    monkeypatch.setattr(deepline, "DeeplineV2Client", FakeClient)
    monkeypatch.setattr(deepline.subprocess, "run", fail_cli)

    result = deepline.deepline_execute("hunter_email_finder", {"domain": "acme.com"})

    assert result["operation"] == "hunter_email_finder"
    assert result["payload"] == {"domain": "acme.com"}
    assert result["include_tool_metadata"] is True


def test_top_level_package_defaults_to_v2_with_lazy_legacy_compatibility():
    import deepline_gtm_agent

    assert deepline_gtm_agent.__all__ == ["DeeplineV2Client", "create_gtm_agent"]
    assert hasattr(deepline_gtm_agent, "DeeplineV2Client")
    assert callable(deepline_gtm_agent.create_gtm_agent)


def test_public_example_uses_native_v2_client():
    from pathlib import Path

    source = Path("example.py").read_text()

    assert "DeeplineV2Client" in source
    assert "create_gtm_agent" not in source
    assert "agent.invoke" not in source


def test_native_stream_tool_calls_are_captured_for_evals():
    calls = _tool_calls_from_native_stream_chunk(
        'data: {"type":"tool-call","toolName":"exa_search","input":{"query":"stripe"}}\n\n'
    )

    assert len(calls) == 1
    assert calls[0].tool_name == "deepline_call"
    assert calls[0].tool_id == "exa_search"
    assert calls[0].payload_keys == ["query"]

def test_eval_runner_can_call_hermes_command():
    reply, calls = asyncio.run(
        run_agent_hermes(
            "hello",
            "python3 -c \"import sys; print('reply:' + sys.argv[1])\"",
            timeout=5,
        )
    )

    assert reply == "reply:hello"
    assert calls == []


def test_native_stream_tool_input_available_events_are_captured_for_evals():
    calls = _tool_calls_from_native_stream_chunk(
        'data: {"type":"tool-input-available","toolName":"serper_google_search","input":{"query":"stripe","num":5}}\n\n'
    )

    assert len(calls) == 1
    assert calls[0].tool_name == "deepline_call"
    assert calls[0].tool_id == "serper_google_search"
    assert calls[0].payload_keys == ["query", "num"]


def test_http_eval_runner_streams_and_captures_tool_calls(monkeypatch):
    seen = {}

    class FakeStreamResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        async def aiter_text(self):
            yield 'data: {"type":"tool-call","toolName":"exa_search","input":{"query":"stripe"}}\n\n'
            yield 'data: {"type":"text-delta","textDelta":"hello"}\n\n'
            yield "data: [DONE]\n\n"

    class FakeStreamContext:
        async def __aenter__(self):
            return FakeStreamResponse()

        async def __aexit__(self, *args):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def stream(self, method, url, **kwargs):
            seen["method"] = method
            seen["url"] = url
            seen["json"] = kwargs.get("json")
            return FakeStreamContext()

        async def post(self, *args, **kwargs):
            raise AssertionError("HTTP eval runner should use /chat/stream")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    reply, calls = asyncio.run(
        run_agent_http("research stripe", "https://agent.example", ToolCallCapture())
    )

    assert seen["method"] == "POST"
    assert seen["url"] == "https://agent.example/chat/stream"
    assert seen["json"]["message"] == "research stripe"
    assert reply == "hello"
    assert [c.tool_id for c in calls] == ["exa_search"]
