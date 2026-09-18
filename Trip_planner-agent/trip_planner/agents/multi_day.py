"""Adaptive multi-day trip planner with conversational memory."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import google_search

from trip_planner.config import MODEL_NAME
from trip_planner.prompts.day_trip import MULTI_DAY_DESCRIPTION, MULTI_DAY_INSTRUCTION


def create_multi_day_trip_agent() -> Agent:
    """Create the Progressive Multi-Day Trip Planner agent."""
    return Agent(
        name="multi_day_trip_agent",
        model=MODEL_NAME,
        description=MULTI_DAY_DESCRIPTION,
        instruction=MULTI_DAY_INSTRUCTION,
        tools=[google_search],
    )


multi_day_trip_agent = create_multi_day_trip_agent()
