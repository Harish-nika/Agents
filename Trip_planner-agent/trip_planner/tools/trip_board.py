"""Publish structured trip board for the side map / spine UI."""

from __future__ import annotations

from google.adk.tools import ToolContext

from trip_planner.runtime.cards import add_card


def publish_trip_board(
    origin: str,
    stops: str,
    start_date: str,
    end_date: str,
    notes: str,
    tool_context: ToolContext,
) -> dict:
    """Publish the ordered trip plan to the UI map and left timeline.

    Call this once you know the trip stops (after understanding the user, ideally
    in the same turn as climate/places). Stops must be comma-separated in travel order.

    Args:
        origin: Where the trip starts from, e.g. "Bengaluru".
        stops: Comma-separated destinations in visit order, e.g.
            "Jog Falls, Murudeshwar, Gokarna".
        start_date: Trip start YYYY-MM-DD (on-site or departure day).
        end_date: Trip end / return YYYY-MM-DD.
        notes: Optional short itinerary note (day flow). Pass "" if none.
        tool_context: ADK tool context (injected).
    """
    print(
        f"TOOL CALLED: publish_trip_board(origin='{origin}', stops='{stops}', "
        f"{start_date}→{end_date})"
    )
    stop_list = [s.strip() for s in stops.split(",") if s.strip()]
    # Full route including origin at start if not already first stop
    route_stops = []
    if origin and origin.strip():
        o = origin.strip()
        if not stop_list or stop_list[0].lower() != o.lower():
            route_stops.append(o)
    route_stops.extend(stop_list)
    # Return to origin if distinct
    if origin and stop_list and stop_list[-1].lower() != origin.strip().lower():
        route_stops.append(origin.strip())

    card = {
        "type": "trip_board",
        "title": "Trip board",
        "origin": origin.strip() if origin else "",
        "stops": stop_list,
        "route_stops": route_stops,
        "start_date": start_date.strip()[:10],
        "end_date": end_date.strip()[:10],
        "notes": notes or "",
        "summary": f"{origin} → {' → '.join(stop_list)}" if stop_list else origin,
    }
    add_card(card)
    return {"status": "success", **card}
