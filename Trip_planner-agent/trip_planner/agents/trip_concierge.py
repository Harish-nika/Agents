"""Multi-turn Trip Guide — orchestrator + specialist AgentTools."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from trip_planner.agents.guide_team import (
    build_directions_specialist,
    build_places_specialist,
    build_stays_specialist,
    build_weather_specialist,
)
from trip_planner.config import MODEL_NAME, resolve_model, tool_capable_model
from trip_planner.prompts.concierge_chat import (
    TRIP_CONCIERGE_DESCRIPTION,
    TRIP_CONCIERGE_INSTRUCTION,
)
from trip_planner.tools.trip_board import publish_trip_board
from trip_planner.tools.trip_prefs import publish_trip_prefs


def build_trip_guide(model: str | None = None) -> Agent:
    """Create Trip Guide orchestrator with weather/places/stays/directions specialists."""
    mid = model or MODEL_NAME
    specialist_mid = tool_capable_model(mid)
    weather = build_weather_specialist(specialist_mid)
    places = build_places_specialist(specialist_mid)
    stays = build_stays_specialist(specialist_mid)
    directions = build_directions_specialist(specialist_mid)
    return Agent(
        name="trip_guide",
        model=resolve_model(mid),
        description=TRIP_CONCIERGE_DESCRIPTION,
        instruction=TRIP_CONCIERGE_INSTRUCTION,
        tools=[
            publish_trip_board,
            publish_trip_prefs,
            AgentTool(agent=weather),
            AgentTool(agent=places),
            AgentTool(agent=stays),
            AgentTool(agent=directions),
        ],
    )


trip_concierge = build_trip_guide()
