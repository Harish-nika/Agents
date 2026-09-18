"""Spontaneous day trip agent."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import google_search

from trip_planner.config import MODEL_NAME
from trip_planner.prompts.day_trip import DAY_TRIP_DESCRIPTION, DAY_TRIP_INSTRUCTION


def create_day_trip_agent() -> Agent:
    """Create the Spontaneous Day Trip Generator agent."""
    return Agent(
        name="day_trip_agent",
        model=MODEL_NAME,
        description=DAY_TRIP_DESCRIPTION,
        instruction=DAY_TRIP_INSTRUCTION,
        tools=[google_search],
    )


day_trip_agent = create_day_trip_agent()
