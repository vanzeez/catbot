"""Tavily wrapper with timeout and retry. Shape recorded in docs/FINDINGS.md (pending live)."""

from __future__ import annotations

import asyncio
from typing import Any

from catbot.integrations._retry import retry_async


async def search(query: str, api_key: str, max_results: int = 5) -> list[dict[str, Any]]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)

    async def once() -> dict[str, Any]:
        return await asyncio.wait_for(
            asyncio.to_thread(client.search, query, max_results=max_results), timeout=15
        )

    raw = await retry_async(once)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:500],
        }
        for r in (raw.get("results") or [])[:max_results]
    ]
