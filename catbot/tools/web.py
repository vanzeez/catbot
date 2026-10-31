"""web_search via Tavily, top 5, origin=web."""

from __future__ import annotations

from catbot.contracts import ToolResult
from catbot.integrations.tavily import search


async def web_search(query: str, api_key: str) -> tuple[list[str], ToolResult]:
    argv = ["tavily", query]
    if not api_key:
        return argv, ToolResult(
            ok=False, summary="web search unavailable", error="no TAVILY_API_KEY", origin="web"
        )
    try:
        results = await search(query, api_key, max_results=5)
    except Exception as exc:  # noqa: BLE001
        return argv, ToolResult(ok=False, summary="web search failed", error=str(exc), origin="web")
    top = results[0]["title"] if results else "no results"
    return argv, ToolResult(
        ok=True, summary=f"{len(results)} results: {top}", data={"results": results}, origin="web"
    )
