"""Specialist tools: web search backed (works with Gemini or Groq)."""

from __future__ import annotations

from google.adk.tools import ToolContext

from trip_planner.runtime.cards import add_card
from trip_planner.tools.web_search import format_search_results, web_search


def _card_from_search(title: str, card_type: str, data: dict) -> str:
    text = format_search_results(data)
    results = (data.get("results") or [])[:6]
    links = [
        {
            "title": (r.get("title") or "").strip(),
            "url": (r.get("url") or "").strip(),
            "snippet": (r.get("snippet") or "").strip(),
        }
        for r in results
        if (r.get("title") or r.get("url") or r.get("snippet"))
    ]
    items = [
        f"{r.get('title', '')}: {r.get('snippet', '')}"
        for r in results
    ]
    add_card(
        {
            "type": card_type,
            "title": title,
            "summary": text[:400],
            "items": items or [text],
            "links": links,
        }
    )
    return text


async def suggest_food(request: str, tool_context: ToolContext) -> str:
    """Find food or restaurant recommendations. Call when the user asks for food.

    Args:
        request: What kind of food/restaurant and where (city/neighborhood).
            Include budget/vibe prefs from the trip when known.
        tool_context: ADK tool context (injected).
    """
    print(f"TOOL CALLED: suggest_food(request='{request[:80]}...')")
    data = web_search(f"best restaurants {request}", max_results=6)
    return _card_from_search("Food suggestions", "places", data)


async def suggest_places(request: str, tool_context: ToolContext) -> str:
    """Suggest sightseeing places/activities for a trip.

    Args:
        request: Destination(s), dates/context, and interests for place ideas.
            Include budget/vibe/pace prefs from the trip when known.
        tool_context: ADK tool context (injected).
    """
    print(f"TOOL CALLED: suggest_places(request='{request[:80]}...')")
    data = web_search(f"best rated places to visit {request}", max_results=8)
    return _card_from_search("Place ideas", "places", data)


async def search_lodging(request: str, tool_context: ToolContext) -> str:
    """Search for hotels or accommodations.

    Args:
        request: City, dates, budget, and lodging preferences.
        tool_context: ADK tool context (injected).
    """
    print(f"TOOL CALLED: search_lodging(request='{request[:80]}...')")
    data = web_search(f"best hotels stays {request}", max_results=6)
    return _card_from_search("Lodging ideas", "lodging", data)
