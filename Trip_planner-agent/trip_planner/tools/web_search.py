"""Free web search via DuckDuckGo (no API key)."""

from __future__ import annotations

from typing import Any


def web_search(query: str, max_results: int = 6) -> dict[str, Any]:
    """Search the public web for places, travel tips, food, or lodging info.

    Args:
        query: Search query, e.g. "best rated places Gokarna Jog Falls Murudeshwar".
        max_results: Max number of results (default 6).

    Returns:
        A dict with status and a list of title/url/snippet results.
    """
    print(f"TOOL CALLED: web_search(query='{query[:100]}...')")
    try:
        from duckduckgo_search import DDGS

        rows: list[dict[str, str]] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max(1, min(max_results, 10))):
                rows.append(
                    {
                        "title": item.get("title") or "",
                        "url": item.get("href") or item.get("link") or "",
                        "snippet": item.get("body") or item.get("snippet") or "",
                    }
                )
        if not rows:
            return {"status": "error", "message": "No search results.", "results": []}
        return {"status": "success", "query": query, "results": rows}
    except Exception as e:
        return {"status": "error", "message": f"Web search failed: {e}", "results": []}


def format_search_results(data: dict[str, Any]) -> str:
    if data.get("status") != "success":
        return data.get("message") or "Search failed."
    lines = []
    for i, row in enumerate(data.get("results") or [], 1):
        lines.append(
            f"{i}. {row.get('title', '').strip()}\n"
            f"   {row.get('snippet', '').strip()}\n"
            f"   {row.get('url', '').strip()}"
        )
    return "\n".join(lines) if lines else "No results."
