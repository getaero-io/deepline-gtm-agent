import inspect
import asyncio

import httpx

from deepline_gtm_agent.v2_client import DeeplineV2Client, extract_text_from_stream_chunk
from tests.run_evals import _tool_calls_from_native_stream_chunk


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


def test_legacy_deepline_execute_is_v2_only():
    import deepline_gtm_agent.deepline as deepline

    source = inspect.getsource(deepline)
    assert "subprocess" not in source
    assert "/api/v2/integrations/{operation}/execute" not in source


def test_native_stream_tool_calls_are_captured_for_evals():
    calls = _tool_calls_from_native_stream_chunk(
        'data: {"type":"tool-call","toolName":"exa_search","input":{"query":"stripe"}}\n\n'
    )

    assert len(calls) == 1
    assert calls[0].tool_name == "deepline_call"
    assert calls[0].tool_id == "exa_search"
    assert calls[0].payload_keys == ["query"]
