"""Publish structured trip board for the side map / spine UI."""

from __future__ import annotations

import re
from datetime import date

from google.adk.tools import ToolContext

from trip_planner.runtime.cards import add_card


_SPLIT_STOPS = re.compile(
    r"\s*(?:,|/|;|\||→|->|–|—|\bto\b|\bthen\b|\band\b)\s*",
    re.IGNORECASE,
)


def _parse_stop_list(stops: str) -> list[str]:
    """Split messy model output into individual place names."""
    raw = (stops or "").strip()
    if not raw:
        return []
    parts = [p.strip(" .") for p in _SPLIT_STOPS.split(raw) if p and p.strip(" .")]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if len(p) < 2:
            continue
        key = p.lower()
        if key in seen:
            continue
        if key in {"start", "return", "trip", "via"}:
            continue
        seen.add(key)
        out.append(p)
    return out


def _normalize_year(ymd: str) -> str:
    """If the model invents a past year, bump to current/next year."""
    text = (ymd or "").strip()[:10]
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if not m:
        return text
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    today = date.today()
    try:
        date(y, mo, d)
    except ValueError:
        return text
    if y >= today.year:
        return text
    try:
        bumped = date(today.year, mo, d)
    except ValueError:
        bumped = date(today.year, mo, min(d, 28))
    if bumped < today:
        try:
            bumped = date(today.year + 1, mo, d)
        except ValueError:
            bumped = date(today.year + 1, mo, min(d, 28))
    return bumped.isoformat()


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
    in the same turn as climate/places). Prefer comma-separated destinations
    (arrows like "A → B → C" are also accepted and split).

    Args:
        origin: Where the trip starts from, e.g. "Bengaluru".
        stops: Destinations in visit order, e.g. "Gokarna, Dandeli, Murudeshwar"
            (not one full-route string).
        start_date: Trip start YYYY-MM-DD (on-site or departure day).
        end_date: Trip end / return YYYY-MM-DD.
        notes: Optional short itinerary note (day flow). Pass "" if none.
        tool_context: ADK tool context (injected).
    """
    print(
        f"TOOL CALLED: publish_trip_board(origin='{origin}', stops='{stops}', "
        f"{start_date}→{end_date})"
    )
    stop_list = _parse_stop_list(stops)
    origin_clean = (origin or "").strip()
    dest_stops = [
        s
        for s in stop_list
        if not origin_clean or s.lower() != origin_clean.lower()
    ]
    if not dest_stops and stop_list:
        dest_stops = stop_list

    start_n = _normalize_year(start_date)
    end_n = _normalize_year(end_date)

    route_stops: list[str] = []
    if origin_clean:
        route_stops.append(origin_clean)
    for s in dest_stops:
        if not route_stops or route_stops[-1].lower() != s.lower():
            route_stops.append(s)
    if (
        origin_clean
        and route_stops
        and route_stops[-1].lower() != origin_clean.lower()
    ):
        route_stops.append(origin_clean)

    card = {
        "type": "trip_board",
        "title": "Trip board",
        "origin": origin_clean,
        "stops": dest_stops,
        "route_stops": route_stops,
        "start_date": start_n,
        "end_date": end_n,
        "notes": notes or "",
        "summary": (
            f"{origin_clean} → {' → '.join(dest_stops)}" if dest_stops else origin_clean
        ),
    }
    add_card(card)
    summary = card.get("summary") or "Trip board updated."
    return {
        "status": "success",
        "message": (
            f"Trip board published for the UI: {summary}. "
            f"Dates {card['start_date']} → {card['end_date']}. "
            "Do NOT paste this JSON to the user — continue with weather/places tools, "
            "then write a short natural-language reply."
        ),
        "summary": summary,
        "start_date": card["start_date"],
        "end_date": card["end_date"],
        "stop_count": len(dest_stops),
    }
