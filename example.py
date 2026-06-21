"""Minimal Deepline v2 native chat example.

Run with:
    DEEPLINE_API_KEY=dlp_... python example.py
"""

from __future__ import annotations

import asyncio

from deepline_gtm_agent.v2_client import DeeplineV2Client, extract_text_from_stream_chunk


async def main() -> None:
    client = DeeplineV2Client()
    prompt = "Research rippling.com and summarize why it might fit a GTM data workflow."
    parts: list[str] = []

    async for chunk in client.stream_agent(
        {
            "prompt": prompt,
            "messages": [{"role": "user", "content": prompt}],
            "response_mode": "stream",
        }
    ):
        text = extract_text_from_stream_chunk(chunk)
        if text:
            print(text, end="", flush=True)
            parts.append(text)

    if parts:
        print()


if __name__ == "__main__":
    asyncio.run(main())
