"""P1 smoke: one Tavily search, print the shape."""

from __future__ import annotations

from _smoke_common import need, settings, show


def main() -> None:
    need(settings.has_tavily, "TAVILY_API_KEY")
    from tavily import TavilyClient

    r = TavilyClient(api_key=settings.tavily_api_key.get_secret_value()).search(
        "Ship Happens hackathon Delhi", max_results=5
    )
    show("keys", list(r.keys()))
    show("first result", r["results"][0] if r.get("results") else None)


if __name__ == "__main__":
    main()
