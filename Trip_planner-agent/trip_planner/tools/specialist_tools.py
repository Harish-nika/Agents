"""Specialist tools: OSM POIs (coords) + DuckDuckGo links (free)."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from google.adk.tools import ToolContext

from trip_planner.runtime.cards import add_card
from trip_planner.tools.geocode import geocode_place
from trip_planner.tools.osm_pois import (
    Kind,
    fetch_pois_along_stops,
    fetch_pois_near,
    guess_location_from_request,
)
from trip_planner.tools.web_search import format_search_results, web_search


def _extract_locations(request: str) -> list[str]:
    """Pull one or more destination names from a specialist request."""
    text = (request or "").strip()
    locs: list[str] = []
    seen: set[str] = set()

    def _add(name: str | None) -> None:
        if not name:
            return
        key = name.lower().strip()
        if len(key) < 2 or key in seen:
            return
        seen.add(key)
        locs.append(name.strip())

    # Split on common separators in multi-stop requests
    chunks = re.split(r"[,;/|]+|\band\b|\bthen\b|→|->", text, flags=re.I)
    for chunk in chunks:
        guessed = guess_location_from_request(chunk.strip())
        _add(guessed)
    if not locs:
        _add(guess_location_from_request(text))
    return locs[:4]


def _pois_for_request(request: str, kind: Kind, limit_per: int = 5) -> list[dict[str, Any]]:
    """Fetch OSM POIs at hubs and midpoints when the trip has multiple stops."""
    locs = _extract_locations(request)
    if not locs:
        return []

    # Multi-stop / "on the way" → corridor samples (stops + midpoints)
    wants_route = bool(
        re.search(
            r"\b(on the way|along the (route|way)|en route|between|via)\b",
            request or "",
            re.I,
        )
    )
    if len(locs) >= 2 or wants_route:
        try:
            return fetch_pois_along_stops(
                locs[:4],
                kind=kind,
                limit_total=max(limit_per, 10),
                max_samples=4,
            )
        except Exception as e:
            print(f"along-route pois skip: {e}")

    # Single hub fallback
    loc = locs[0]
    try:
        geo = geocode_place(loc)
    except Exception as e:
        print(f"osm geocode skip: {e}")
        return []
    if not geo:
        return []
    radius = 10000 if kind == "places" else 8000
    try:
        batch = fetch_pois_near(
            float(geo["latitude"]),
            float(geo["longitude"]),
            kind=kind,
            radius_m=radius,
            limit=limit_per,
        )
    except Exception as e:
        print(f"osm fetch skip: {e}")
        return []
    return [{**p, "near": geo.get("name") or loc} for p in batch]


def _format_pois_text(pois: list[dict[str, Any]]) -> str:
    if not pois:
        return ""
    along = any(p.get("along_route") or p.get("on_the_way") for p in pois)
    lines = [
        "OpenStreetMap along the route:" if along else "OpenStreetMap nearby:"
    ]
    for p in pois[:10]:
        near = p.get("near") or ""
        dist = p.get("distance_km")
        bit = f"- {p.get('icon', '')} {p['name']} ({p.get('category', '')}"
        if near:
            bit += f" — {near}"
        if dist is not None:
            bit += f", {dist} km from sample"
        if p.get("on_the_way"):
            bit += ", on the way"
        bit += ")"
        lines.append(bit)
    return "\n".join(lines)


def _card_from_search(
    title: str,
    card_type: str,
    data: dict,
    *,
    pois: list[dict[str, Any]] | None = None,
    kind: Kind = "places",
) -> str:
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
    poi_list = pois or []
    poi_text = _format_pois_text(poi_list)
    if poi_text:
        text = f"{poi_text}\n\nWeb references:\n{text}" if text else poi_text
        for p in poi_list:
            items.insert(
                0,
                f"{p.get('icon', '')} {p['name']} — {p.get('category', '')} "
                f"({p.get('near', '')}, {p.get('distance_km', '?')} km)",
            )
    add_card(
        {
            "type": card_type,
            "title": title,
            "summary": text[:500],
            "items": items or [text],
            "links": links,
            "pois": poi_list,
            "poi_kind": kind,
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
    # Parallel + off event loop so SSE stays alive during Overpass/DDG
    pois_r, data = await asyncio.gather(
        asyncio.to_thread(_pois_for_request, request, "food", 5),
        asyncio.to_thread(web_search, f"best restaurants {request}", 6),
        return_exceptions=True,
    )
    if isinstance(pois_r, BaseException):
        pois_r = []
    if isinstance(data, BaseException):
        data = {"status": "error", "results": []}
    return _card_from_search(
        "Food suggestions", "places", data, pois=pois_r or [], kind="food"
    )


async def suggest_places(request: str, tool_context: ToolContext) -> str:
    """Suggest sightseeing places/activities for a trip.

    Args:
        request: Destination(s), dates/context, and interests for place ideas.
            Include budget/vibe/pace prefs from the trip when known.
        tool_context: ADK tool context (injected).
    """
    print(f"TOOL CALLED: suggest_places(request='{request[:80]}...')")

    async def _search() -> dict:
        data = await asyncio.to_thread(
            web_search, f"{request} tourist attractions India", 8
        )
        if data.get("status") != "success" or not data.get("results"):
            data = await asyncio.to_thread(web_search, request, 8)
        return data

    pois_r, data = await asyncio.gather(
        asyncio.to_thread(_pois_for_request, request, "places", 5),
        _search(),
        return_exceptions=True,
    )
    if isinstance(pois_r, BaseException):
        print(f"osm pois skip: {pois_r}")
        pois_r = []
    if isinstance(data, BaseException):
        print(f"web search skip: {data}")
        data = {"status": "error", "results": []}
    return _card_from_search(
        "Place ideas", "places", data, pois=pois_r or [], kind="places"
    )


async def search_lodging(request: str, tool_context: ToolContext) -> str:
    """Search for hotels or accommodations.

    Args:
        request: City, dates, budget, and lodging preferences.
        tool_context: ADK tool context (injected).
    """
    print(f"TOOL CALLED: search_lodging(request='{request[:80]}...')")
    pois_r, data = await asyncio.gather(
        asyncio.to_thread(_pois_for_request, request, "lodging", 5),
        asyncio.to_thread(web_search, f"best hotels stays {request}", 6),
        return_exceptions=True,
    )
    if isinstance(pois_r, BaseException):
        pois_r = []
    if isinstance(data, BaseException):
        data = {"status": "error", "results": []}
    return _card_from_search(
        "Lodging ideas", "lodging", data, pois=pois_r or [], kind="lodging"
    )
