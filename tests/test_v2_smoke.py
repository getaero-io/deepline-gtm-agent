import os
import asyncio

import pytest

from deepline_gtm_agent.v2_client import DeeplineV2Client


@pytest.mark.live
def test_live_tool_execute_contract():
    if not os.environ.get("DEEPLINE_API_KEY"):
        pytest.skip("DEEPLINE_API_KEY required")

    result = asyncio.run(
        DeeplineV2Client().execute_tool(
            "test_company_search",
            {"domain": "stripe.com"},
        )
    )

    assert result.get("status") in {"completed", "success", "ok"}
    assert "toolResponse" in result or "result" in result


@pytest.mark.live
def test_live_deeplineagent_stream_contract():
    if not os.environ.get("DEEPLINE_API_KEY"):
        pytest.skip("DEEPLINE_API_KEY required")

    async def collect():
        chunks = []
        async for chunk in DeeplineV2Client().stream_agent(
            {"prompt": "Say ok in one word.", "maxToolCalls": 0}
        ):
            chunks.append(chunk)
            if len(chunks) >= 3:
                break
        return chunks

    chunks = asyncio.run(collect())

    assert chunks
