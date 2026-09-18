"""Publish structured trip preferences for the UI and specialist prompts."""

from __future__ import annotations

from google.adk.tools import ToolContext

from trip_planner.runtime.cards import add_card


def publish_trip_prefs(
    budget: str,
    pace: str,
    interests: str,
    companions: str,
    vibe: str,
    notes: str,
    tool_context: ToolContext,
) -> dict:
    """Save trip preferences so the UI and specialists can personalize results.

    Call when the user states budget, pace, interests, companions, or vibe
    (e.g. "budget trip, chill pace, beaches"). Pass "" for unknown fields.

    Args:
        budget: e.g. "budget", "mid-range", "luxury", or "".
        pace: e.g. "chill", "moderate", "packed", or "".
        interests: Comma-separated interests, e.g. "beaches, temples, food".
        companions: e.g. "solo", "couple", "family", "friends", or "".
        vibe: Short mood, e.g. "relaxed coastal", "adventure", or "".
        notes: Any other preference notes, or "".
        tool_context: ADK tool context (injected).
    """
    print(
        f"TOOL CALLED: publish_trip_prefs(budget='{budget}', pace='{pace}', "
        f"interests='{interests}', vibe='{vibe}')"
    )
    interest_list = [s.strip() for s in (interests or "").split(",") if s.strip()]
    card = {
        "type": "trip_prefs",
        "title": "Trip preferences",
        "budget": (budget or "").strip(),
        "pace": (pace or "").strip(),
        "interests": interest_list,
        "companions": (companions or "").strip(),
        "vibe": (vibe or "").strip(),
        "notes": (notes or "").strip(),
        "summary": ", ".join(
            x
            for x in [
                (budget or "").strip(),
                (pace or "").strip(),
                (vibe or "").strip(),
                ", ".join(interest_list),
            ]
            if x
        ),
    }
    add_card(card)
    return {"status": "success", **card}
