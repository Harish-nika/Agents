"""Google Directions tool + shareable Maps URL."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote_plus

import requests

from trip_planner.runtime.cards import add_card

_VALID_MODES = {"driving", "walking", "bicycling", "transit"}


def _maps_dir_url(origin: str, destination: str, mode: str) -> str:
    travelmode = mode if mode in _VALID_MODES else "driving"
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={quote_plus(origin)}"
        f"&destination={quote_plus(destination)}"
        f"&travelmode={travelmode}"
    )


def get_directions(
    origin: str,
    destination: str,
    mode: str = "transit",
) -> dict[str, Any]:
    """Get route directions between two places (driving, transit, walking, or bicycling).

    Args:
        origin: Starting address or place name.
        destination: Ending address or place name.
        mode: One of driving, transit, walking, bicycling. Default transit.

    Returns:
        Summary, step list, duration/distance, and a Google Maps URL.
    """
    print(
        f"TOOL CALLED: get_directions(origin='{origin}', destination='{destination}', "
        f"mode='{mode}')"
    )
    mode = (mode or "transit").lower().strip()
    if mode not in _VALID_MODES:
        mode = "transit"

    maps_url = _maps_dir_url(origin, destination, mode)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

    if not api_key or api_key == "your_maps_api_key_here":
        result = {
            "status": "partial",
            "message": (
                "GOOGLE_MAPS_API_KEY not set — returning Maps link only. "
                "Add a key for detailed transit/driving steps."
            ),
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "maps_url": maps_url,
            "steps": [],
        }
        add_card(
            {
                "type": "map",
                "title": f"Route — {origin} → {destination}",
                "summary": f"Open in Google Maps ({mode})",
                "maps_url": maps_url,
                "mode": mode,
                "origin": origin,
                "destination": destination,
                "embed_query": f"{origin} to {destination}",
                "steps": [],
            }
        )
        return result

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/directions/json",
            params={
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "key": api_key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status != "OK":
            hint = {
                "REQUEST_DENIED": (
                    "Directions API denied this key — enable Directions API, turn on billing, "
                    "and allow this key for Directions. You can still open the route in Maps."
                ),
                "OVER_QUERY_LIMIT": "Directions quota exceeded. Try again later or open Maps link.",
                "ZERO_RESULTS": "No route found for that origin/destination/mode.",
            }.get(status, f"Directions API status: {status}")
            result = {
                "status": "error",
                "message": hint,
                "maps_url": maps_url,
                "origin": origin,
                "destination": destination,
                "mode": mode,
            }
            add_card(
                {
                    "type": "map",
                    "title": f"Route — {origin} → {destination}",
                    "summary": hint,
                    "maps_url": maps_url,
                    "mode": mode,
                    "origin": origin,
                    "destination": destination,
                    "embed_query": f"{origin} to {destination}",
                    "steps": [],
                }
            )
            return result

        route = data["routes"][0]
        leg = route["legs"][0]
        steps = []
        for step in leg.get("steps") or []:
            # strip simple HTML from instructions
            instr = step.get("html_instructions", "")
            for tag in ("<b>", "</b>", "<div>", "</div>", "<wbr/>", "<wbr>"):
                instr = instr.replace(tag, " ")
            while "<" in instr and ">" in instr:
                start = instr.find("<")
                end = instr.find(">", start)
                if end == -1:
                    break
                instr = instr[:start] + " " + instr[end + 1 :]
            steps.append(
                {
                    "instruction": " ".join(instr.split()),
                    "distance": (step.get("distance") or {}).get("text"),
                    "duration": (step.get("duration") or {}).get("text"),
                    "travel_mode": step.get("travel_mode"),
                }
            )

        summary = (
            f"{leg.get('duration', {}).get('text', '?')} · "
            f"{leg.get('distance', {}).get('text', '?')} · {mode}"
        )
        result = {
            "status": "success",
            "origin": leg.get("start_address", origin),
            "destination": leg.get("end_address", destination),
            "mode": mode,
            "duration": (leg.get("duration") or {}).get("text"),
            "distance": (leg.get("distance") or {}).get("text"),
            "summary": summary,
            "steps": steps,
            "maps_url": maps_url,
        }
        add_card(
            {
                "type": "map",
                "title": f"Route — {origin} → {destination}",
                "summary": summary,
                "maps_url": maps_url,
                "mode": mode,
                "origin": result["origin"],
                "destination": result["destination"],
                "embed_query": f"{origin} to {destination}",
                "steps": steps[:12],
            }
        )
        return result
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Directions request failed: {e}",
            "maps_url": maps_url,
        }
